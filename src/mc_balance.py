# mc_balance.py — Monte Carlo balance harness (standalone)
from __future__ import annotations
from dataclasses import dataclass
from statistics import mean
import random
from typing import Optional

# --- Imports projet ---
from core.stats import Stats
from core.player import Player
from game.game_loop import GameLoop
from core.attack import Attack
from core import data_loader
from core.entity import Entity
import time


# ----------------- Config -----------------
NUM_TRIALS_PER_LEVEL = 100    # ex: 200 combats par niveau
LEVELS = list(range(1, 11))   # niveaux de zone testés 1..10
BASE_SEED = 4242              # seed globale pour reproductibilité
PLAYER_CLASS_KEY = "guerrier" # adapte si nécessaire
BASE_ATK = 8
BASE_DEF = 4
BASE_LCK = 2
BASE_CRIT = 2.0
PLAYER_HP_MAX = 35
PLAYER_SP_MAX = 12

_CACHE = {}
PERF = {
    "build_game": 0.0,
    "warm_cache": 0.0,
    "pick_enemy": 0.0,
    "fresh_player": 0.0,
    "choose_attack": 0.0,
    "resolve_player": 0.0,
    "resolve_enemy": 0.0,
    "simulate_fight": 0.0,
}
# ------------------------------------------

@dataclass
class FightStats:
    wins: int = 0
    turns: list[int] = None
    dmg_taken: list[int] = None
    dmg_dealt: list[int] = None

    def __post_init__(self):
        self.turns = [] if self.turns is None else self.turns
        self.dmg_taken = [] if self.dmg_taken is None else self.dmg_taken
        self.dmg_dealt = [] if self.dmg_dealt is None else self.dmg_dealt

def _build_game(level: int, seed: int, player: Player) -> GameLoop:
    t0 = time.perf_counter()
    g = GameLoop(player=player, io=None, seed=seed, initial_zone=None, start_level=level)
    hydrate_game_with_cache(g)
    PERF["build_game"] += time.perf_counter() - t0
    return g

def _pick_enemy(game: GameLoop) -> Entity:
    # Choix d’un blueprint au hasard, puis build au niveau courant
    t0 = time.perf_counter()
    rng = game.rng
    if not hasattr(game, "_mc_enemy_pool"):
        pool = list(getattr(game, "enemy_blueprints", {}).values())
        if not pool:
            raise RuntimeError("Aucun EnemyBlueprint chargé.")
        game._mc_enemy_pool = pool
    bp = rng.choice(game._mc_enemy_pool)
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
        PERF["choose_attack"] += time.perf_counter() - t0
        return None
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

    while game.player.is_alive() and enemy.is_alive():
        # --- tour du joueur ---
        atk = _choose_best_attack(game, enemy, dmg_cache)
        if atk is None:
            # pas d’attaque -> tour perdu (devrait être rare)
            pass
        else:
            res = game.engine.resolve_turn(game.player, enemy, atk)
            dmg_dealt += max(0, res.damage_dealt)
            if not enemy.is_alive():
                turns += 1
                break

        # --- tour de l’ennemi (s’il vit encore) ---
        eatk = game._select_enemy_attack(enemy)
        res_e = game.engine.resolve_turn(enemy, game.player, eatk)
        dmg_taken += max(0, res_e.damage_dealt)
        turns += 1

    PERF["simulate_fight"] += time.perf_counter() - t_sim
    win = (not enemy.is_alive()) and (game.player.is_alive())
    return win, turns, dmg_taken, dmg_dealt

def run_mc():
    random.seed(BASE_SEED)
    table: dict[int, FightStats] = {L: FightStats() for L in LEVELS}

    for L in LEVELS:
        seed0 = BASE_SEED + (L * 100000)
        g = _build_game(L, seed0, _fresh_player(f"InitL{L}"))
        for i in range(NUM_TRIALS_PER_LEVEL):
            seed = seed0 + i

            g.player.restore_all()
            if hasattr(g, "effects"):
                try: g.effects.clear_all(g.player)
                except Exception: pass


            g.engine.rng.seed(seed)
            g.rng.seed(seed ^ 0x9E3779B1)
            win, t, dtaken, ddealt = simulate_fight(g, seed)

            fs = table[L]
            if win:
                fs.wins += 1
            fs.turns.append(t)
            fs.dmg_taken.append(dtaken)
            fs.dmg_dealt.append(ddealt)

    # Affichage
    print("\n=== Monte Carlo Balance Report ===")
    print(f"Trials per level: {NUM_TRIALS_PER_LEVEL}")
    print(f"Player: class={PLAYER_CLASS_KEY} base=ATK {BASE_ATK} DEF {BASE_DEF} LCK {BASE_LCK} CRITx{BASE_CRIT} HP={PLAYER_HP_MAX} SP={PLAYER_SP_MAX}")
    header = f"{'Lvl':>3} | {'WR%':>5} | {'TTKμ':>5} | {'TTKσ':>5} | {'DTakenμ':>8} | {'DDealtμ':>8}"
    print(header)
    print("-" * len(header))
    for L in LEVELS:
        fs = table[L]
        n = NUM_TRIALS_PER_LEVEL
        wr = 100.0 * fs.wins / max(1, n)
        mu_t = mean(fs.turns) if fs.turns else 0.0
        # écart-type simple (sans stats import), calcule approx
        if len(fs.turns) > 1:
            m = mu_t
            var = sum((x - m) ** 2 for x in fs.turns) / (len(fs.turns) - 1)
            sd_t = var ** 0.5
        else:
            sd_t = 0.0
        mu_taken = int(round(mean(fs.dmg_taken))) if fs.dmg_taken else 0
        mu_dealt = int(round(mean(fs.dmg_dealt))) if fs.dmg_dealt else 0
        print(f"{L:>3} | {wr:5.1f} | {mu_t:5.2f} | {sd_t:5.2f} | {mu_taken:>8} | {mu_dealt:>8}")

    # --- Récap temps ---
    total = sum(PERF.values()) or 1.0
    print("\n--- Timings ---")
    for k in ("warm_cache","build_game","fresh_player", "simulate_fight","pick_enemy","choose_attack","resolve_player","resolve_enemy"):
        print(f"{k:>15}: {PERF[k]:7.3f}s  ({PERF[k]/total*100:5.1f}%)")


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
