from __future__ import annotations
"""Boucle haut-niveau: zones/sections, choix RNG, enchaînement des combats.

- Aucune I/O directe (utilise GameIO).
"""


from dataclasses import dataclass
import random
from enum import Enum, auto
from typing import Callable, Protocol, Any, TYPE_CHECKING
from collections.abc import Sequence
import copy

from core.player import Player
from core.enemy import Enemy
from core.stats import Stats
from core.attack import Attack
from core.combat import CombatEngine
from core.combat import CombatResult, CombatContext, CombatEvent
from core.effect_manager import EffectManager
from core.effects import Effect
from core.loadout import LoadoutManager
from content.actions import default_loadout_for_class
from core.inventory import Inventory
from core.supply import Wallet
from core.supply import SupplyManager
from content.shop_offers import build_offers, REST_HP_PCT, REST_SP_PCT, REPAIR_COST_PER_POINT, ShopOffer
from core.event_engine import EventEngine
from core.save import save_to_file, load_from_file
from core.data_loader import load_enemy_blueprints, load_encounter_tables, load_equipment_banks, load_equipment_zone_index
from content.effects_bank import make_effect
from core.equipment import Weapon



# =========================
# Types / Interfaces d'I/O
# =========================

class GameIO(Protocol):
    """Interface d'I/O pour brancher une UI (console, PyGame, etc.). Toutes les méthodes sont optionnelles."""
    # Combats
    def on_battle_start(self, player: Player, enemy: Enemy) -> None: ...
    def on_battle_end(self, player: Player, enemy: Enemy, victory: bool) -> None: ...
    def present_events(self, result: CombatResult) -> None: ...
    def show_status(self, player: Player, enemy: Enemy) -> None: ...
    def choose_player_attack(self, player: Player, enemy: Enemy) -> Attack: ...
    def choose_player_action(self, player: Player, enemy:  Enemy, *, attacks: Sequence[Attack], inventory: Inventory) -> tuple[str, Any]: ...
    # Zones / Sections
    def on_zone_start(self, zone: Zone) -> None: ...
    def on_zone_cleared(self, zone: Zone) -> None: ...
    def choose_section(self, zone: Zone, options: Sequence[Section]) -> Section: ...
    def choose_supply_action(self, player: Player, *, wallet: Wallet, offers: list[ShopOffer]): ...
    def choose_shop_purchase(self, offers: list[ShopOffer], *, wallet:Wallet): ...
    def choose_event_option(self, text: str, options: Sequence[str]): ...
    def choose_next_zone(self, options: Sequence[ZoneType]) -> ZoneType: ...
    def present_text(self, text: str) -> None: ...


# ================
# Zones / Sections
# ================

class SectionType(Enum):
    COMBAT = auto()
    EVENT = auto()
    SUPPLY = auto()
    BOSS = auto()

class ZoneType(Enum):
    RUINS = auto()
    CAVES = auto()
    FOREST = auto()
    DESERT = auto()
    SWAMP = auto()

@dataclass
class ZoneState:
    zone_type: ZoneType
    level: int
    explored: int = 0
    boss_defeated: bool = False

    def boss_forced(self) -> bool:
        return self.explored >= 4 and not self.boss_defeated

# --- Tirage de 2 types distincts ---
def next_zone_options(current: ZoneType, rng: random.Random, k: int = 3) -> list[ZoneType]:
    """Propose k zones suivantes, distinctes et ≠ current si possible."""
    all_types = list(ZoneType)
    pool = [z for z in all_types if z != current] or all_types
    rng.shuffle(pool)
    return pool[:max(1, min(k, len(pool)))]

ZONE_TYPE_LIST: list[ZoneType] = [ZoneType.RUINS, ZoneType.CAVES, ZoneType.FOREST, ZoneType.DESERT, ZoneType.SWAMP]

@dataclass
class Section:
    """Une section à explorer dans une zone."""
    kind: SectionType
    # Pour COMBAT/BOSS, une fabrique d'ennemi ; pour EVENT/SUPPLY, None.
    enemy_factory: Callable[[], Enemy] | None = None

@dataclass
class Zone:
    """État courant d'une zone en cours d'exploration."""
    zone_type: ZoneType
    level: int  # profondeur/progression globale (sert à scaler les ennemis)
    explored: int = 0  # nombre de sections *non-boss* déjà explorées (0..4)

    @property
    def boss_ready(self) -> bool:
        """Vrai quand on a exploré 4 sections ; la 5e est le boss."""
        return self.explored >= 4


# ===================
# Boucle principale
# ===================

class GameLoop:
    """Contrôleur principal : enchaîne sections et zones selon les règles."""

    def __init__(
        self,
        player: Player,
        io: GameIO | None = None,
        *,
        seed: int | None = None,
        initial_zone: ZoneType | None = None,
        start_level: int = 1,
    ) -> None:
        self.player = player
        self.io = io
        self.rng = random.Random(seed)
        # Zone courante
        self.zone = Zone(zone_type=initial_zone or self._rng_choice(ZONE_TYPE_LIST), level=start_level)
        self.zone_state = ZoneState(zone_type=self.zone.zone_type, level=self.zone.level)
        self.equip_zone_index = load_equipment_zone_index()
        self.effects = EffectManager()
        self.player_inventory = Inventory(capacity=12)
        self.loadouts = LoadoutManager()
        self.wallet = Wallet(50)
        try:
            class_key = getattr(self.player, "player_class_key", "guerrier")
            self.loadouts.set(self.player, default_loadout_for_class(class_key))
        except Exception:
            pass
        self.event_engine = EventEngine(
            data_dir="data/events",
            lang="fr",
            seed=seed,
            effects=self.effects,
            enemy_factory=None
            )
        self.engine = CombatEngine(seed=seed)  # CombatEngine gère crits, usure, etc.
        self.enemy_blueprints = load_enemy_blueprints(getattr(self, "attacks_reg", {}))
        self.encounter_tables = load_encounter_tables()
        self.weapon_bank, self.armor_bank, self.artifact_bank = load_equipment_banks()
        self.running = True

    # -------------
    # Entrée / Run
    # -------------
    def run(self) -> None:
        """Boucle principale. S'arrête si le joueur meurt ou si on set running=False."""
        while self.running and self.player.hp > 0:
            # Début de zone
            if self.io:
                self.io.on_zone_start(self.zone)

            # 4 sections "libres" (COMBAT/EVENT/SUPPLY), puis BOSS
            while self.running and self.player.hp > 0 and not self.zone.boss_ready:
                options = self._generate_section_choices(self.zone)
                section = self._choose_section(options)
                self._enter_section(section)
                # Si on est encore en vie et que ce n'était pas un boss => on a exploré 1 section
                if self.player.hp > 0 and section.kind != SectionType.BOSS:
                    self.zone.explored += 1

            # Boss (5e section), si on est encore en vie
            if self.running and self.player.hp > 0:
                boss_section = self._generate_boss_section(self.zone)
                self._enter_section(boss_section)

            # Fin de zone
            if self.player.hp <= 0 or not self.running:
                break
            if self.io:
                self.io.on_zone_cleared(self.zone)

            # Choix de 3 zones suivantes (types distincts)
            next_zone_type = self._choose_next_zone(self.zone)
            # Progression du level (peut impacter le scaling ennemi)
            self.zone = Zone(zone_type=next_zone_type, level=self.zone.level + 1)

    # ----------------------
    # Génération / Choix RNG
    # ----------------------

    def _generate_section_choices(self, zone: Zone) -> list[Section]:
        """Propose 2 sections de types différents parmi COMBAT/EVENT/SUPPLY (jamais 2 fois le même)."""
        pool = [SectionType.COMBAT, SectionType.EVENT, SectionType.SUPPLY]
        a = self._rng_choice(pool)
        if a == SectionType.SUPPLY:
            pool.remove(SectionType.SUPPLY)
            b = self._rng_choice(pool)
        b = self._rng_choice([t for t in pool if t != a])  # <-- toujours différent
        return [self._make_section(zone, a), self._make_section(zone, b)]

    def _generate_boss_section(self, zone: Zone) -> Section:
        return self._make_section(zone, SectionType.BOSS)

    def _choose_section(self, options: Sequence[Section]) -> Section:
        """Délègue à l'I/O si dispo, sinon première option par défaut."""
        if self.io:
            return self.io.choose_section(self.zone, options)
        return options[0]

    def _on_section_cleared(self, section_type: SectionType) -> None:
        if section_type != SectionType.BOSS:
            self.zone_state.explored += 1

    def _after_boss_and_pick_next_zone(self) -> None:
        self.zone_state.boss_defeated = True
        opts = next_zone_options(self.zone_state.zone_type, self.rng, k=3)
        if self.io and hasattr(self.io, "choose_next_zone"):
            idx = self.io.choose_next_zone(opts)  # renvoie 0..k-1
            idx = max(0, min(idx, len(opts)-1))
            new_type = opts[idx]
        else:
            new_type = opts[0]
        # reset zone: +1 niveau et sections réinitialisées
        self.zone_state = ZoneState(zone_type=new_type, level=self.zone_state.level + 1)

    def _choose_next_zone(self, current_zone: Zone) -> ZoneType:
        """Après boss, propose 3 zones de types distincts (différents possibles du courant)."""
        pool = [z for z in ZONE_TYPE_LIST if z != current_zone.zone_type] or ZONE_TYPE_LIST  # on peut autoriser la répétition du type courant si tu veux l'exclure: retire-le
        # On tire 3 différents
        options = self.rng.sample(pool, k=min(3, len(pool)))
        if self.io:
            return self.io.choose_next_zone(options)
        return options[0]

    # -----------------
    # Entrée dans section
    # -----------------

    def _make_section(self, zone: Zone, kind: SectionType) -> Section:
        if kind in (SectionType.COMBAT, SectionType.BOSS):
            is_boss = (kind == SectionType.BOSS)
            return Section(kind=kind, enemy_factory=lambda: self._spawn_enemy(zone, is_boss=is_boss))
        # EVENT / SUPPLY → pas d'ennemi
        return Section(kind=kind, enemy_factory=None)

    def _enter_section(self, section: Section) -> None:
        """Exécute la section selon son type. Les parties non-combat restent TODO."""
        if section.kind == SectionType.COMBAT:
            self._run_battle(section.enemy_factory() if section.enemy_factory else self._spawn_enemy(self.zone))
        elif section.kind == SectionType.BOSS:
            self._run_battle(section.enemy_factory() if section.enemy_factory else self._spawn_enemy(self.zone, is_boss=True))
        elif section.kind == SectionType.EVENT:
            self._handle_event_section()
        elif section.kind == SectionType.SUPPLY:
            self._handle_supply_section()

    # -------------
    # Combat (moteur)
    # -------------

    def _run_battle(self, enemy: Enemy) -> None:
        """Boucle d'un combat jusqu'au K.O. (UI via GameIO)."""
        if self.io:
            self.io.on_battle_start(self.player, enemy)

        while self.player.hp > 0 and enemy.hp > 0 and self.running:
            # --- Tour du joueur ---
            act_kind, payload = self._choose_player_action(enemy)
            if act_kind == "item":
                res_p = self._use_item_in_combat(payload) # payload = item_id
            elif act_kind == "attack":
                p_attack: Attack = payload
                res_p = self.engine.resolve_turn(self.player, enemy, p_attack)
                # On gère les effets player
                self._apply_attack_effects(attacker=self.player, defender=enemy, attack=p_attack, result=res_p)

            # On gère l'affichage I/O
            if self.io:
                self.io.present_events(res_p)
                self.io.show_status(self.player, enemy)
            if enemy.hp <= 0 or self.player.hp <= 0:
                break
            # Fin du tour du joueur; tick les effets
            self._tick_end_of_turn(attacker=self.player, defender=enemy)


            # --- Tour de l'ennemi ---
            e_attack = self._select_enemy_attack(enemy)
            res_e = self.engine.resolve_turn(enemy, self.player, e_attack)

            # On gère les effets enemies
            self._apply_attack_effects(attacker=enemy, defender=self.player, attack=e_attack, result=res_e)

            # On gère l'affichage I/O
            if self.io:
                self.io.present_events(res_e)
                self.io.show_status(self.player, enemy)
            if enemy.hp <= 0 or self.player.hp <= 0:
                break
            # Fin du tour de l'enemie; tick les effets
            self._tick_end_of_turn(attacker=enemy, defender=self.player)

        # fin du combat
        victory = (self.player.hp > 0 and enemy.hp <= 0)
        if victory:
            g = self._gold_reward_for(enemy, is_boss=getattr(enemy, "is_boss", False))
            self._grant_gold(g)
        if self.io:
            self.io.on_battle_end(self.player, enemy, victory=(self.player.hp > 0 and enemy.hp <= 0))
        if self.io:
            self.io.present_text(f"[DEBUG] Après combat → HP {self.player.hp}/{self.player.max_hp}, "
                                f"SP {self.player.sp}/{self.player.max_sp}")
    
    def _gather_player_attacks(self) -> list[Attack]:
        atks: list[Attack] = []
        # depuis le loadout
        lo = self.loadouts.get(self.player)
        if lo and getattr(lo, "primary", None): atks.append(lo.primary)
        if lo and getattr(lo, "skill", None):   atks.append(lo.skill)
        if lo and getattr(lo, "utility", None): atks.append(lo.utility)
        # attaque de classe
        if self.player.player_class.class_attack:
            atks.append(self.player.player_class.class_attack)
        # attaques d'arme
        if self.player.weapon.bonus_attack:
            atks.append(self.player.weapon.bonus_attack)
        return atks

    def _choose_player_action(self, enemy: Enemy) -> tuple[str, Any]:
        """Renvoie ('attack', Attack) ou ('item', item_id)."""
        atks = self._gather_player_attacks()
        if self.io:
            res = self.io.choose_player_action(self.player, enemy, attacks=atks, inventory=self.player_inventory)
            # tolérance: si l’IO renvoie un Attack tout seul
            if not isinstance(res, tuple):
                return ("attack", res)
            return res
        # fallback: première attaque dispo
        return ("attack", atks[0] if atks else Attack(name="Attaque", base_damage=5, variance=2, cost=0))

    def _select_enemy_attack(self, enemy: Enemy) -> Attack:
        if getattr(enemy, "attacks", None):
            atks = enemy.attacks; ws = getattr(enemy, "attack_weights", [1]*len(atks))
            pairs = list(zip(atks, ws))
            total = sum(ws)
            r = self.rng.uniform(0, total); acc = 0.0
            for atk, w in pairs:
                acc += w
                if r <= acc:
                    return atk
            return atks[-1]
        return Attack(name="Coup maladroit", base_damage=4, variance=2, cost=0)
    
    def _use_item_in_combat(self, item_id: str) -> CombatResult:
        events: list[CombatEvent] = []
        ctx = CombatContext(attacker=self.player, defender=None, events=events)  # defender None: action utilitaire
        item_events = self.player_inventory.use_consumable(item_id, user=self.player, ctx=ctx)
        events.append(item_events)
        # Utiliser un objet consomme le tour, n'inflige pas de dégâts
        return CombatResult(events=events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False)

    def _apply_attack_effects(self, attacker: Player | Enemy, defender: Player | Enemy, attack: Attack, result: CombatResult):
        """Applique les effets listés sur `attack` si l'attaque a touché.

        - on_hit(ctx) est appelé pour des effets *immédiats* (ex.: dégâts bonus).
        - Si l'effet a une `duration` > 0, on l'enregistre pour des ticks futurs.
        """
        if result.defender_alive:
            if not attack.effects:
                return
            # Choix de la cible: par défaut sur le défenseur; si attack.target == "self", sur l'attaquant
            target = attacker if getattr(attack, "target", "enemy") == "self" else defender

            # Contexte d'événements pour le log
            events = []
            ctx = CombatContext(attacker=attacker, defender=defender, events=events)

            for eff in attack.effects:
                e2 = self._clone_effect_instance(eff)   # <-- NOUVEAU : clone par application
                try:
                    self.effects.apply(target, e2, source_name=f"attack:{attack.name}", ctx=ctx)
                except Exception:
                    # fallback hyper sûr : applique “à sec”
                    e2.on_apply(target, ctx)

            # on pousse les logs dans le flux d’événements courant
            if self.io and events:
                self.io.present_events(CombatResult(events=events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))
        
    def _tick_end_of_turn(self, attacker, defender):
        if self.effects is None:
            return
        events: list[CombatEvent] = []
        ctx = CombatContext(attacker=attacker, defender=defender, events=events)
        self.effects.on_turn_end(attacker, ctx)
        if self.io and events:
            self.io.present_events(CombatResult(events=events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))

    # --------------------------
    # Événements / Ravitaillement
    # --------------------------

    def _handle_event_section(self) -> None:
        """Présente un évènement data-driven et applique le choix."""
        # 1) choisir un événement compatible avec la zone courante
        ev = self.event_engine.pick_for_zone(self.zone.zone_type.name)
        if ev is None:
            # fallback: rien de spécial
            if self.io:
                self.io.present_events(CombatResult(events=[CombatEvent(text="Rien d'inhabituel ici.", tag="event_none")],
                                                    attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))
            return

        # 2) demander le choix à l'IO (ou prendre la première option)
        if self.io and hasattr(self.io, "choose_event_option"):
            chosen_id = self.io.choose_event_option(ev.text, [o.label for o in ev.options])
            # la méthode IO peut renvoyer un index (int) ou un id (str) selon ton implémentation
            if isinstance(chosen_id, int):
                chosen_id = ev.options[max(0, min(chosen_id, len(ev.options)-1))].id
        else:
            chosen_id = ev.options[0].id

        # 3) appliquer l'option choisie
        res = self.event_engine.apply_option(
            ev,
            option_id=chosen_id,
            player=self.player,
            wallet=self.wallet,
            extra_ctx={"zone": self.zone},
        )

        # 4) afficher les logs
        if self.io and res.events:
            self.io.present_events(CombatResult(events=res.events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))

        # 5) démarrer un combat si l'évènement le demande
        if res.start_combat:
            # simple mapping: si "boss": True -> boss; sinon combat normal
            is_boss = bool(res.start_combat.get("boss", False))
            enemy = self._spawn_enemy(self.zone, is_boss=is_boss)
            self._run_battle(enemy)

    def _handle_supply_section(self) -> None:
        """Ravitaillement: repos, réparation, achats (parchemin d’attaque de classe inclus)."""
        mgr = SupplyManager(self.player_inventory, self.wallet, self.loadouts)
        class_key = getattr(self.player, "player_class_key", "guerrier")
        offers: list[ShopOffer] = build_offers(zone_level=self.zone.level, player_class_key=class_key)  
        offers = [o for o in offers if self._is_allowed(o)]

        # Si l'IO sait présenter un menu Supply, on le laisse piloter
        if self.io and hasattr(self.io, "choose_supply_action"):
            running = True
            while running:
                action = self.io.choose_supply_action(self.player, wallet=self.wallet, offers=offers)
                if action == "REST":
                    res = mgr.do_rest(self.player, hp_pct=REST_HP_PCT, sp_pct=REST_SP_PCT)
                elif action == "REPAIR":
                    res = mgr.repair_all_you_can_afford(self.player, price_per_point=REPAIR_COST_PER_POINT)
                elif action == "SHOP":
                    # laisser l’IO sélectionner une offre + quantité
                    if hasattr(self.io, "choose_shop_purchase"):
                        choice = self.io.choose_shop_purchase(offers, wallet=self.wallet)
                        if choice is None:
                            res = None
                        else:
                            offer, qty = choice
                            res = mgr.buy_offer(self.player, offer, qty=qty)
                    else:
                        res = None
                elif action == "SAVE":
                    ok = save_to_file(self, "save_slot_1.json")
                    if self.io:
                        msg = "Sauvegarde réussie." if ok else "Échec de sauvegarde."
                        self.io.present_text(msg)
                elif action == "LOAD":
                    loaded = load_from_file("save_slot_1.json", io=self.io)
                    if loaded:
                        # On remplace l’état courant par celui chargé (simplest path)
                        self.__dict__.update(loaded.__dict__)
                        if self.io:
                            self.io.present_text("Partie chargée.")
                    else:
                        if self.io:
                            self.io.present_text("Impossible de charger le fichier.")
                else:  # "LEAVE" ou inconnu
                    break

                if res is not None and self.io:
                    self.io.present_events(CombatResult(events=res.events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))
        else:
            # Fallback simple: repos gratuit et on sort
            res = mgr.do_rest(self.player, hp_pct=REST_HP_PCT, sp_pct=REST_SP_PCT)
            if self.io:
                self.io.present_events(CombatResult(events=res.events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))

    # -------------
    # Utilitaires
    # -------------

    def _spawn_enemy(self, zone: Zone, is_boss: bool = False):
        # 1) essai via encounter tables (si présentes)
        zkey = zone.zone_type.name  # ex "RUINS"
        table = self.encounter_tables.get(zkey)
        if table:
            bucket = table["boss"] if is_boss else table["normal"]
            if bucket:
                pairs = [(row["enemy_id"], int(row.get("weight", 1))) for row in bucket]
                enemy_id = self._weighted_pick(pairs)
                bp = self.enemy_blueprints.get(enemy_id)
                if bp:
                    return bp.build(level=zone.level)

        # 2) fallback: ton ancienne logique
        return self._spawn_enemy_fallback(zone, is_boss)
    
    def _spawn_enemy_fallback(self, zone: Zone, *, is_boss: bool = False) -> Enemy:
        """Fabrique un ennemi en fonction du type de zone et du niveau (scaling simple)."""
        # Ex. scaling très simple (à équilibrer selon ton jeu)
        lvl = zone.level
        hp = 40 + 10 * lvl + (30 if is_boss else 0)
        atk = 7 + 2 * lvl + (5 if is_boss else 0)
        dfs = 4 + 2 * lvl + (3 if is_boss else 0)
        luck = 3 + lvl

        name = {
            ZoneType.RUINS: "Garde des Ruines" if is_boss else "Pillard des Ruines",
            ZoneType.CAVES: "Seigneur des Cavernes" if is_boss else "Rongeur cavernicole",
            ZoneType.FOREST: "Esprit de la Forêt" if is_boss else "Bandit sylvestre",
            ZoneType.DESERT: "Prince des Dunes" if is_boss else "Charognard du désert",
            ZoneType.SWAMP: "Souverain des Marais" if is_boss else "Boueux affamé",
        }[zone.zone_type]

        return Enemy(
            name=name,
            base_stats=Stats(attack=atk, defense=dfs, luck=luck),
            base_hp_max=hp,
            base_sp_max=0,
        )
    
    def _rng_choice(self, seq: Sequence) -> any:
        return seq[self.rng.randrange(0, len(seq))]

    def _clone_effect_instance(self, eff: Effect) -> Effect:
        """Retourne une nouvelle instance d'effet avec la même config.
        1) On essaye via effects_bank.make_effect(effect_id ou name).
        2) Sinon deepcopy (moins idéal si l'effet garde des refs contextuelles).
        """
        try:
            return make_effect(eff.id, eff.duration, eff.potency)
        except Exception:
            return copy.deepcopy(eff)
        
    def _weighted_pick(self, pairs: list[tuple[str, int]]) -> str:
        total = sum(w for _, w in pairs) or 1
        r = self.rng.uniform(0, total)
        acc = 0.0
        for eid, w in pairs:
            acc += w
            if r <= acc:
                return eid
        return pairs[-1][0]

    def _gold_reward_for(self, enemy: Enemy, is_boss: bool) -> int:
        """Calcule l'or gagné. Si le blueprint de l'ennemi fournit des bornes, on les utilise.
        Sinon: formule par défaut en fonction du niveau + stats."""
        # 1) si tu construis l'ennemi depuis un blueprint, garde son id sur l'instance:
        # setattr(e, "enemy_id", self.enemy_id)  ← à faire dans EnemyBlueprint.build()
        reward = None
        eid = getattr(enemy, "enemy_id", None)
        if eid and hasattr(self, "enemy_blueprints"):
            bp = self.enemy_blueprints.get(eid)
            if bp and hasattr(bp, "gold_min") and hasattr(bp, "gold_max"):
                lo = int(getattr(bp, "gold_min"))
                hi = int(getattr(bp, "gold_max"))
                if hi < lo: hi = lo
                reward = self.rng.randint(lo, hi)

        if reward is None:
            # 2) fallback: niveau + stats
            lvl = getattr(self.zone, "level", 1)
            atk = getattr(enemy.base_stats, "attack", 0)
            df  = getattr(enemy.base_stats, "defense", 0)
            base = 8 + 2*lvl + (atk + df)//4
            jitter = self.rng.uniform(0.85, 1.15)
            reward = max(1, int(base * jitter))

        if is_boss:
            reward = int(reward * 4)  # prime boss
        return reward

    def _grant_gold(self, amount: int) -> None:
        self.wallet.add(amount)
        if self.io:
            self.io.present_text(f"+{amount} or ramassé.")
    
    def _is_allowed(self, offer: ShopOffer) -> bool:
        """Filtre d'offres du shop selon l'état de la partie."""
        # exemple: on n’affiche pas le parchemin de classe si le joueur en a déjà une
        if offer.kind == "class_scroll" and getattr(self.player, "class_attack", None):
            return False

        # exemple: items toujours autorisés (tu peux ajouter des règles d’inventaire ici)
        if offer.kind == "item":
            return True

        # fallback
        return True
