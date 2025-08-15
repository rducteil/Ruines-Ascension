from __future__ import annotations
"""Boucle haut-niveau: zones/sections, choix RNG, enchaînement des combats.

- Aucune I/O directe (utilise GameIO).
"""


from dataclasses import dataclass
import random
from enum import Enum, auto
from typing import Callable, List, Optional, Protocol, Sequence, Tuple, Any

from core.player import Player
from core.enemy import Enemy
from core.stats import Stats
from core.attack import Attack
from core.combat import CombatEngine
from core.combat_types import CombatResult, CombatContext, CombatEvent
from core.effect_manager import EffectManager
from core.loadout_manager import LoadoutManager
from content.actions import default_loadout_for_class
from core.inventory import Inventory
from core.wallet import Wallet
from core.supply import SupplyManager
from content.shop_offers import build_offers, REST_HP_PCT, REST_SP_PCT, REPAIR_COST_PER_POINT, ShopOffer
from core.event_engine import EventEngine


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
    def on_zone_start(self, zone: "Zone") -> None: ...
    def on_zone_cleared(self, zone: "Zone") -> None: ...
    def choose_section(self, zone: "Zone", options: Sequence["Section"]) -> "Section": ...
    def choose_supply_action(self, player: Player, *, wallet: Wallet, offers: list[ShopOffer]): ...
    def choose_shop_purchase(self, offers: list[ShopOffer], *, wallet:Wallet): ...
    def choose_event_option(self, text: str, options: Sequence[str]): ...
    def choose_next_zone(self, options: Sequence["ZoneType"]) -> "ZoneType": ...


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
    zone_type: "ZoneType"
    level: int
    explored: int = 0
    boss_defeated: bool = False

    def boss_forced(self) -> bool:
        return self.explored >= 4 and not self.boss_defeated

# --- Tirage de 2 types distincts selon des poids ---
def _weighted_sample_two_distinct(items: Sequence["SectionType"],
                                  weights: Sequence[float],
                                  rng: random.Random) -> tuple["SectionType", "SectionType"]:
    assert len(items) == len(weights) >= 2
    total = sum(weights)
    r = rng.uniform(0, total)
    acc = 0.0
    first = items[-1]
    for it, w in zip(items, weights):
        acc += w
        if r <= acc:
            first = it
            break
    # retirer 'first'
    items2, weights2 = [], []
    for it, w in zip(items, weights):
        if it != first:
            items2.append(it)
            weights2.append(w)
    total2 = sum(weights2)
    r2 = rng.uniform(0, total2)
    acc2 = 0.0
    second = items2[-1]
    for it, w in zip(items2, weights2):
        acc2 += w
        if r2 <= acc2:
            second = it
            break
    return first, second

def section_choices_for(zone: ZoneState, rng: random.Random,
                        weights: dict["SectionType", float] | None = None) -> list["SectionType"]:
    """Retourne 1 ou 2 choix de section.
    - Si boss forcé (après 4 sections): [BOSS]
    - Sinon: 2 types distincts parmi {COMBAT, EVENT, SUPPLY}.
    """
    if zone.boss_forced():
        return [SectionType.BOSS]

    w = weights or {
        SectionType.COMBAT: 0.5,
        SectionType.EVENT:  0.25,
        SectionType.SUPPLY: 0.25,
    }
    items = [SectionType.COMBAT, SectionType.EVENT, SectionType.SUPPLY]
    ws = [w[it] for it in items]
    a, b = _weighted_sample_two_distinct(items, ws, rng)
    return [a, b]

def next_zone_options(current: "ZoneType", rng: random.Random, k: int = 3) -> list["ZoneType"]:
    """Propose k zones suivantes, distinctes et ≠ current si possible."""
    all_types = list(ZoneType)
    pool = [z for z in all_types if z != current] or all_types
    rng.shuffle(pool)
    return pool[:max(1, min(k, len(pool)))]

ZONE_TYPE_LIST: List[ZoneType] = [ZoneType.RUINS, ZoneType.CAVES, ZoneType.FOREST, ZoneType.DESERT, ZoneType.SWAMP]

@dataclass
class Section:
    """Une section à explorer dans une zone."""
    kind: SectionType
    # Pour COMBAT/BOSS, une fabrique d'ennemi ; pour EVENT/SUPPLY, None.
    enemy_factory: Optional[Callable[[], Enemy]] = None

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
        io: Optional[GameIO] = None,
        *,
        seed: Optional[int] = None,
        initial_zone: Optional[ZoneType] = None,
        start_level: int = 1,
    ) -> None:
        self.player = player
        self.io = io
        self.rng = random.Random(seed)
        # Zone courante
        self.zone = Zone(zone_type=initial_zone or self._rng_choice(ZONE_TYPE_LIST), level=start_level)
        self.zone_state = ZoneState(zone_type=self.zone.zone_type, level=self.zone.level)
        self.effects = EffectManager()
        self.player_inventory = Inventory(capacity=12)
        self.loadouts = LoadoutManager()
        try:
            from core.settings import START_GOLD
            self.wallet = Wallet(START_GOLD)
        except Exception:
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

    def _generate_section_choices(self, zone: Zone) -> List[Section]:
        """Propose 2 sections de types différents parmi COMBAT/EVENT/SUPPLY (jamais 2 fois le même)."""
        pool = [SectionType.COMBAT, SectionType.EVENT, SectionType.SUPPLY]
        a = self._rng_choice(pool)
        b = self._rng_choice([t for t in pool if t != a])  # <-- toujours différent
        return [self._make_section(zone, a), self._make_section(zone, b)]

    def _generate_boss_section(self, zone: Zone) -> Section:
        return self._make_section(zone, SectionType.BOSS)

    def _choose_next_section_type(self) -> "SectionType":
        choices = section_choices_for(self.zone_state, self.rng)
        if self.io and hasattr(self.io, "choose_next_section"):
            idx = self.io.choose_next_section(choices)  # renvoie 0..len(choices)-1
            idx = max(0, min(idx, len(choices)-1))
            return choices[idx]
        # fallback: si boss forcé il n'y en a qu'un ; sinon on prend le premier
        return choices[0]

    def _choose_section(self, options: Sequence[Section]) -> Section:
        """Délègue à l'I/O si dispo, sinon première option par défaut."""
        if self.io and hasattr(self.io, "choose_section"):
            return self.io.choose_section(self.zone, options)
        return options[0]

    def _on_section_cleared(self, section_type: "SectionType") -> None:
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
        pool = [z for z in ZONE_TYPE_LIST]  # on peut autoriser la répétition du type courant si tu veux l'exclure: retire-le
        # On tire 3 différents
        options = self.rng.sample(pool, k=min(3, len(pool)))
        if self.io and hasattr(self.io, "choose_next_zone"):
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
            else:
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

        if self.io:
            self.io.on_battle_end(self.player, enemy, victory=(self.player.hp > 0 and enemy.hp <= 0))
    
    def _choose_player_action(self, enemy: Enemy) -> Tuple[str, Any]:
        """Renvoie ('attack', Attack) ou ('item', item_id)."""
        # 1) Si l'IO offre un menu d'action complet, on l'utilise
        if self.io and hasattr(self.io, "choose_player_action"):
            return self.io.choose_player_action(self.player, enemy,
                                                attacks=self._list_player_attacks(),
                                                inventory=self.player_inventory)

        # 2) Fallback : ancien comportement (attaque seulement)
        return ("attack", self._list_player_attacks()[0])

    def _select_player_attack(self, enemy: Enemy) -> Attack:
        if self.io and hasattr(self.io, "choose_player_attack"):
            return self.io.choose_player_attack(self.player, enemy)
        # Fallback : arme → attaque spéciale si dispo ; sinon attaque basique
        weapon = getattr(self.player, "weapon", None)
        if weapon and hasattr(weapon, "get_available_attacks"):
            specials = weapon.get_available_attacks()  # type: ignore[attr-defined]
            if specials:
                return specials[0]
        return Attack(name="Attaque", base_damage=5, variance=2, cost=0)

    def _select_enemy_attack(self, enemy: Enemy) -> Attack:
        # TODO: brancher une vraie IA (enemy.choose_action)
        return Attack(name="Griffe", base_damage=4, variance=1, cost=0)
    
    def _use_item_in_combat(self, item_id: str) -> CombatResult:
        events: list[CombatEvent] = []
        ctx = CombatContext(attacker=self.player, defender=None, events=events)  # defender None: action utilitaire
        item_events = self.player_inventory.use_consumable(item_id, user=self.player, ctx=ctx)
        events.extend(item_events)
        # Utiliser un objet consomme le tour, n'inflige pas de dégâts
        return CombatResult(events=events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False)

    def _apply_attack_effects(self, attacker, defender, attack: Attack, result: CombatResult):
        """Applique les effets listés sur `attack` si l'attaque a touché.

        - on_hit(ctx) est appelé pour des effets *immédiats* (ex.: dégâts bonus).
        - Si l'effet a une `duration` > 0, on l'enregistre pour des ticks futurs.
        """
        if self.effects is None or result.damage_dealt <= 0:
            return
        target_entity = attacker if getattr(attack, "target", "enemy") == "self" else defender
        events = result.events
        ctx = CombatContext(attacker=attacker, defender=target_entity, events=events, damage_dealt=result.damage_dealt, was_crit=result.was_crit)
        for eff in getattr(attack, "effects", []):
            eff.on_hit(ctx)
            if getattr(eff, "duration", 0) > 0:
                self.effects.apply(target_entity, eff, source_name=attack.name, ctx=ctx)
        
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
        offers = build_offers(zone_level=self.zone.level, player_class_key=class_key)

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

    def _spawn_enemy(self, zone: Zone, *, is_boss: bool = False) -> Enemy:
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

    def _list_player_attacks(self) -> list[Attack]:
        opts: list[Attack] = []
        weapon = getattr(self.player, "weapon", None)
        if weapon and hasattr(weapon, "get_available_attacks"):
            specials = weapon.get_available_attacks()
            if specials: opts.extend(specials)
        class_attack = getattr(self.player, "class_attack", None)
        if class_attack: opts.append(class_attack)
        opts.append(Attack(name="Attaque basique", base_damage=5, variance=2, cost=0))
        return opts