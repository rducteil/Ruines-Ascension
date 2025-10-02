# mc_balance.py — Monte Carlo balance harness (standalone)
from __future__ import annotations
from dataclasses import dataclass
from statistics import mean
import random, time, copy, gc
from typing import Optional
from functools import lru_cache

# --- Imports projet ---
from core.stats import Stats
from core.player import Player
from game.game_loop import GameLoop
from core.attack import Attack
from core import data_loader
from core.entity import Entity
import time


# ----------------- Config -----------------
NUM_TRIALS_PER_LEVEL = 500    # ex: 200 combats par niveau
MAX_TURN_PER_FIGHT = 20
NO_PROGRESS_CAP = 8
LEVELS = list(range(1, 51))   # niveaux de zone testés 1..10
SEED_LIST = [4242, 1337, 9001, 12345, 202502]          
TARGET_WR = 0.65
PLAYER_CLASS_KEY = "guerrier" # adapte si nécessaire
BASE_ATK = 8
BASE_DEF = 4
BASE_LCK = 2
BASE_CRIT = 2.0
PLAYER_HP_MAX = 35
PLAYER_SP_MAX = 12

_CACHE = {}
PERF = {
    "warm_cache": 0.0,
    "build_game": 0.0,
    "fresh_player": 0.0,
    "simulate_fight": 0.0,
    "pick_enemy": 0.0,        
    "choose_attack": 0.0,
    "resolve_player": 0.0,
    "resolve_enemy": 0.0,
    "enemy_builds": 0,       
}

_MC_ENEMY_POOL = None
_MC_ENEMY_KEYS = None
# ------------------------------------------

@dataclass
class FightStats:
    wins: int = 0
    turns: list[int] = None
    dmg_taken: list[int] = None
    dmg_dealt: list[int] = None
    timeouts: int = 0
    culprits: dict[str, int] = None  # enemy_id -> count

    def __post_init__(self):
        self.turns = [] if self.turns is None else self.turns
        self.dmg_taken = [] if self.dmg_taken is None else self.dmg_taken
        self.dmg_dealt = [] if self.dmg_dealt is None else self.dmg_dealt
        self.culprits = {} if self.culprits is None else self.culprits

def _build_game(level: int, seed: int, player: Player) -> GameLoop:
    t0 = time.perf_counter()
    g = GameLoop(player=player, io=None, seed=seed, initial_zone=None, start_level=level)
    hydrate_game_with_cache(g)
    PERF["build_game"] += time.perf_counter() - t0
    return g

@lru_cache(maxsize=None)
def _cached_enemy_proto(enemy_id: str, level: int):
    PERF["enemy_builds"] += 1
    cache = warm_cache()
    bp = cache["enemy_bps"][enemy_id]
    return bp.build(level=level)

def _pick_enemy(game) -> "Entity":
    t0 = time.perf_counter()
    # choix d'un blueprint via sa clé (pas l'objet)
    enemy_id = game.rng.choice(_MC_ENEMY_KEYS)
    # récupère le proto mémoïsé puis clone pour ce combat
    bp = warm_cache()["enemy_bps"][enemy_id]
    e = bp.build(level=game.zone.level)
    PERF["pick_enemy"] += time.perf_counter() - t0
    return e

def _fresh_player(name: str) -> Player:
    """Crée un joueur neuf (stats/HP/SP frais) pour un run MC."""
    t0 = time.perf_counter()
    p = Player(
        name=name,
        player_class_key=PLAYER_CLASS_KEY,
        base_stats=Stats(BASE_ATK, BASE_DEF, BASE_LCK, BASE_CRIT),
        base_hp_max=PLAYER_HP_MAX,
        base_sp_max=PLAYER_SP_MAX,
    )
    
    PERF["fresh_player"] += time.perf_counter() - t0
    return p

def _choose_best_attack(game: GameLoop, enemy, dmg_cache: dict) -> Optional[Attack]:
    # Récupère les attaques dispo du joueur et choisit celle qui maximise l’estimation haute
    t0 = time.perf_counter()
    attacks = game._gather_player_attacks()  # dépend de SP/équipement
    if not attacks:
        basic = None
        for atk in getattr(game, "attacks_reg", {}).values():
            nm = getattr(atk, "name", "").lower()
            if nm in ("frapper", "strike"):
                basic = atk
                break
        PERF["choose_attack"] += time.perf_counter() - t0
        return basic
    # utilise l’estimateur de dégâts du moteur (harmonisé avec resolve_turn)
    scored = []
    for a in attacks:
        key = (
            getattr(enemy, "enemy_id", id(enemy)),
            getattr(a, "attack_id", getattr(a, "name", repr(a)))
        )
        pair = dmg_cache.get(key)
        if pair is None:
            pair = game.engine.estimate_damage(game.player, enemy, a)
            dmg_cache[key] = pair
        lo, hi = pair
        scored.append((hi, a))
    scored.sort(key=lambda t: (t[0], getattr(t[1], "cost", 0)), reverse=True)
    PERF["choose_attack"] += time.perf_counter() - t0
    return scored[0][1]

def simulate_fight(game: GameLoop, seed: int) -> tuple[bool, int, int, int]:
    """
    Retourne (win, turns, dmg_taken_by_player, dmg_dealt_to_enemy).
    Un 'tour' = une action joueur + (si encore en vie) une action ennemi.
    """
    t_sim = time.perf_counter()
    # Reset HP/SP joueur au max pour chaque combat
    game.player.restore_all()

    # Nouveau RNG pour le combat (déterministe par seed)
    game.engine.rng.seed(seed)
    game.rng.seed(seed ^ 0x9E3779B1)

    enemy = _pick_enemy(game)
    turns = 0
    dmg_taken = 0
    dmg_dealt = 0
    dmg_cache = {}
    no_progress = 0
    while game.player.is_alive() and enemy.is_alive() and turns < MAX_TURN_PER_FIGHT and no_progress < NO_PROGRESS_CAP:
        dealt_this = 0
        taken_this = 0
        
        # --- tour du joueur ---
        atk = _choose_best_attack(game, enemy, dmg_cache)
        if atk is None:
            # pas d’attaque -> tour perdu (devrait être rare)
            pass
        else:
            res = game.engine.resolve_turn(game.player, enemy, atk)
            dealt_this = max(0, res.damage_dealt)
            dmg_dealt += dealt_this
            if not enemy.is_alive():
                turns += 1
                no_progress = 0
                break

        # --- tour de l’ennemi (s’il vit encore) ---
        if enemy.is_alive():
            eatk = game._select_enemy_attack(enemy)
            res_e = game.engine.resolve_turn(enemy, game.player, eatk)
            taken_this = max(0, res_e.damage_dealt)
            dmg_taken += taken_this

        # --- progression de tour & stagnation ---
        if dealt_this==0 and taken_this==0:
            no_progress += 1
        else:
            no_progress = 0

        turns += 1

    PERF["simulate_fight"] += time.perf_counter() - t_sim
    timed_out = (turns >= MAX_TURN_PER_FIGHT) or (no_progress >= NO_PROGRESS_CAP)
    win = (not enemy.is_alive()) and (game.player.is_alive()) and (not timed_out)
    enemy_id = getattr(enemy, "enemy_id", "unknown")
    return win, turns, dmg_taken, dmg_dealt, timed_out, enemy_id

def run_mc():
    table = {L: FightStats() for L in LEVELS}

    base_seed = SEED_LIST[0]
    g = _build_game(LEVELS[0], base_seed, _fresh_player(f"InitAll"))
    p = g.player
    print(f"[Snapshot] Guerrier réel: ATK {p.base_stats.attack} DEF {p.base_stats.defense} "
        f"HPmax {p.max_hp} SPmax {p.max_sp}")
    w, a, r = p.equipment.weapon, p.equipment.armor, p.equipment.artifact
    print(f"[Snapshot] Equip: {w.name} (+ATK {getattr(w,'bonus_attack',0)}), "
        f"{a.name} (+DEF {getattr(a,'bonus_defense',0)}), "
        f"{r.name} (+ATK% {getattr(r,'atk_pct',0)}, +DEF% {getattr(r,'def_pct',0)})")


    total_runs = 0
    for base_seed in SEED_LIST:

        random.seed(base_seed)
        g.engine.rng.seed(base_seed)
        g.rng.seed(base_seed ^ 0x9E3779B1)

        for L in LEVELS:
            if hasattr(g, "zone") and hasattr(g.zone, "level"):
                g.zone.level = L

            for i in range(NUM_TRIALS_PER_LEVEL):
                seed = base_seed + (L * 100000) + i

                g.player.restore_all()
                if hasattr(g, "effects"):
                    try: g.effects.clear_all(g.player)
                    except Exception: pass


                g.engine.rng.seed(seed)
                g.rng.seed(seed ^ 0x9E3779B1)


                win, t, dtaken, ddealt, to_flag, eid = simulate_fight(g, seed)

                fs = table[L]
                fs.wins += int(win)
                fs.turns.append(t)
                fs.dmg_taken.append(dtaken)
                fs.dmg_dealt.append(ddealt)
                if to_flag:
                    fs.timeouts += 1
                    fs.culprits[eid] = fs.culprits.get(eid, 0) + 1

                total_runs += 1

                if (i + 1) % 25 == 0:
                    gc.collect()

    # Affichage
    print("\n=== Monte Carlo Balance Report ===")
    print(f"Trials per level: {NUM_TRIALS_PER_LEVEL}")
    print(f"Player: class={PLAYER_CLASS_KEY} base=ATK {BASE_ATK} DEF {BASE_DEF} LCK {BASE_LCK} CRITx{BASE_CRIT} HP={PLAYER_HP_MAX} SP={PLAYER_SP_MAX}")
    
    header = f"{'Lvl':>3} | {'WR%':>5} | {'TTKμ':>5} | {'TTKσ':>5} | {'DTakenμ':>8} | {'DDealtμ':>8}| {'TOs':>3}| {'DWr':>8}"
    print(header)
    print("-" * len(header))

    for L in LEVELS:
        fs = table[L]
        n = max(1, NUM_TRIALS_PER_LEVEL * len(SEED_LIST))
        wr = fs.wins / n
        mu_t = mean(fs.turns) if fs.turns else 0.0
        if len(fs.turns) > 1:
            m = mu_t
            var = sum((x - m) ** 2 for x in fs.turns) / (len(fs.turns) - 1)
            sd_t = var ** 0.5
        else:
            sd_t = 0.0
        mu_taken = int(round(mean(fs.dmg_taken))) if fs.dmg_taken else 0
        mu_dealt = int(round(mean(fs.dmg_dealt))) if fs.dmg_dealt else 0
        delta_wr = int(round((wr - TARGET_WR) * 100))
        print(f"{L:>3} | {100*wr:5.1f} | {mu_t:5.2f} | {sd_t:5.2f} | {mu_taken:>8} | {mu_dealt:>8} | {fs.timeouts:>3} | {delta_wr:>+8}")

    # --- Récap temps ---
    time_keys = ("warm_cache","build_game","fresh_player", "simulate_fight","pick_enemy","choose_attack","resolve_player","resolve_enemy")
    total = sum(PERF[k] for k in time_keys) or 1.0
    print("\n--- Timings ---")
    for k in time_keys:
        print(f"{k:>15}: {PERF[k]:7.3f}s  ({PERF[k]/total*100:5.1f}%)")

    print("\n--- Timeouts (cap de tours atteints) ---")
    for L in LEVELS:
        fs = table[L]
        if fs.timeouts:
            top = sorted(fs.culprits.items(), key=lambda kv: kv[1], reverse=True)[:3]
            top_s = ", ".join([f"{k} x{v}" for k,v in top])
            print(f"Niveau {L}: {fs.timeouts} timeout(s). Ennemis récurrents: {top_s}")


def warm_cache():
    """Charge toutes les données (ennemis, attaques, équipements, items…) une seule fois."""
    t0 = time.perf_counter()
    global _CACHE
    if _CACHE:
        return _CACHE

    attacks = data_loader.load_attacks()
    enemy_bps = data_loader.load_enemy_blueprints(attacks)

    # banques d'équipement sous forme de prototypes enrichis (tier/tags/zones + clone())
    weapon_bank, armor_bank, artifact_bank = data_loader.load_equipment_banks()

    # items.json → dict {item_id: factory()}
    item_factories = data_loader.load_items()

    # (facultatif) tables de rencontre/zone si tu les utilises
    try:
        encounters = data_loader.load_encounter_tables()
    except Exception:
        encounters = {}

    _CACHE = {
        "attacks": attacks,
        "enemy_bps": enemy_bps,
        "weapon_bank": weapon_bank,
        "armor_bank": armor_bank,
        "artifact_bank": artifact_bank,
        "item_factories": item_factories,
        "encounters": encounters,
    }

    out = _CACHE
    global _MC_ENEMY_KEYS
    _MC_ENEMY_KEYS = list(enemy_bps.keys())
    PERF["warm_cache"] += time.perf_counter() - t0
    return _CACHE

def hydrate_game_with_cache(g: GameLoop):
    """Injecte les données pré-chargées dans une instance de GameLoop existante."""
    c = warm_cache()
    g.attacks_reg = c["attacks"]
    g.enemy_blueprints = c["enemy_bps"]
    g.weapon_bank = c["weapon_bank"]
    g.armor_bank = c["armor_bank"]
    g.artifact_bank = c["artifact_bank"]
    g.item_factories = c["item_factories"]
    # si ton GameLoop utilise un index/rencontres :
    if hasattr(g, "encounter_tables"):
        g.encounter_tables = c["encounters"]


if __name__ == "__main__":
    run_mc()
