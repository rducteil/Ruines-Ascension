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
from core.data_loader import load_enemy_blueprints, load_encounter_tables, load_equipment_banks, load_equipment_zone_index, load_items, load_attacks, EnemyBlueprint
from content.effects_bank import make_effect
from core.equipment import Equipment
from core.item import Item



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
    def choose_player_action(self, player: Player, enemy:  Enemy, *, attacks: Sequence[Attack], inventory: Inventory, engine: CombatEngine) -> tuple[str, Any]: ...
    # Zones / Sections
    def on_zone_start(self, zone: Zone) -> None: ...
    def on_zone_cleared(self, zone: Zone) -> None: ...
    def choose_section(self, zone: Zone, options: Sequence[Section]) -> Section: ...
    def choose_supply_action(self, player: Player, *, wallet: Wallet, offers: list[ShopOffer]): ...
    def choose_shop_purchase(self, offers: list[ShopOffer], *, wallet:Wallet): ...
    def choose_event_option(self, text: str, options: Sequence[str]): ...
    def choose_next_zone(self, options: Sequence[ZoneType]) -> ZoneType: ...
    def choose_inventory_equip(self, player, *, inventory: Inventory): ...
    def choose_sell_items(self, inventory: Inventory, *, wallet): ...
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
            class_key = (getattr(self.player, "player_class_key", "guerrier") or "guerrier").strip().lower()
            self.loadouts.set(self.player, default_loadout_for_class(class_key))
        except Exception:
            pass
        self.event_engine = EventEngine(
            data_dir="data",
            lang="fr",
            seed=seed,
            effects=self.effects,
            enemy_factory=None
            )
        self.engine = CombatEngine(seed=seed)  # CombatEngine gère crits, usure, etc.
        self.attacks_reg = load_attacks()
        self.enemy_blueprints = load_enemy_blueprints(self.attacks_reg)
        self.encounter_tables = load_encounter_tables()
        self.weapon_bank, self.armor_bank, self.artifact_bank = load_equipment_banks()
        self.item_factories = load_items()
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
        else:
            b = self._rng_choice([t for t in pool if t != a])
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
        """Exécute la section selon son type"""
        if self.io:
            if section.kind == SectionType.BOSS:
                self.io.present_text("=== ⚠️ BOSS ⚠️ — Section 5/5 ===")
            else:
                self.io.present_text(f"--- Section {self.zone.explored + 1}/5 — {section.kind.name.title()} ---")
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
            self.io.show_status(self.player, enemy)

        while self.player.hp > 0 and enemy.hp > 0 and self.running:
            # --- Tour du joueur ---
            while True:
                act_kind, payload = self._choose_player_action(enemy)
                if act_kind == "item":
                    res_p = self._use_item_in_combat(payload) # payload = item_id
                    break
                elif act_kind == "attack":
                    p_attack: Attack = payload
                    res_p = self.engine.resolve_turn(self.player, enemy, p_attack)
                    # On gère les effets player
                    self._apply_attack_effects(attacker=self.player, defender=enemy, attack=p_attack, result=res_p)
                    break
                elif act_kind == "equip":
                    # payload ex. {"slot":"weapon","index":0}
                    payload = payload or {}
                    idx  = int(payload.get("index", -1))
                    ok, msg = self.player_inventory.equip_equipment_by_index(self.player, idx)
                    # Cette action consomme le tour et n'inflige pas de dégâts
                    if self.io:
                        self.io.present_text(("Équipement: " + msg) if ok else ("Échec: " + msg))
                    continue
                elif act_kind == "inspect":
                    if self.io:
                        self.io.present_text(self._player_sheet(enemy))
                    continue
                elif act_kind == "inventory":
                    sub = payload or {}
                    a = sub.get("action")
                    if a == "equip":
                        idx = int(sub.get("index", -1))
                        ok, msg = self.player_inventory.equip_equipment_by_index(self.player, idx)
                        if self.io:
                            self.io.present_text(("Équipement: " + msg) if ok else ("Échec: " + msg))
                        continue
                    if a == "inspect":
                        if self.io:
                            self.io.present_text(self._player_sheet(enemy))
                        continue
                    if a == "use_item":
                        act_kind = "item"
                        payload = sub.get("item_id")
                        break
                    continue

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

            drops = self._roll_item_drops(enemy, is_boss=getattr(enemy, "is_boss", False))
            if drops:
                self._grant_items(drops)

            eqs = self._roll_equipment_drop(is_boss=getattr(enemy, "is_boss", False))
            if eqs:
                self._grant_equipment(eqs)

        if self.io:
            self.io.on_battle_end(self.player, enemy, victory=(self.player.hp > 0 and enemy.hp <= 0))
    
    def _gather_player_attacks(self) -> list[Attack]:
        atks: list[Attack] = []
        # depuis le loadout
        lo = self.loadouts.get(self.player)
        if lo and getattr(lo, "primary", None): atks.append(lo.primary)
        if lo and getattr(lo, "skill", None):   atks.append(lo.skill)
        if lo and getattr(lo, "utility", None): atks.append(lo.utility)
        # attaque de classe (si débloqué)
        if self.player.player_class.class_attack  and self.player.class_attack_unlocked:
            atks.append(self.player.player_class.class_attack)
        # attaques d'arme
        if self.player.equipment.weapon.bonus_attack:
            atks.append(self.player.equipment.weapon.bonus_attack)
        try:
            for sp in self.player.equipment.weapon.get_available_attacks():
                if isinstance(sp, Attack):
                    atks.append(sp)
        except Exception:
            pass

        # Verification
        atks = [a for a in atks if isinstance(a, Attack)]
        return atks

    def _choose_player_action(self, enemy: Enemy) -> tuple[str, Any]:
        """Renvoie ('attack', Attack) ou ('item', item_id)."""
        atks = self._gather_player_attacks()
        if self.io:
            res = self.io.choose_player_action(self.player, enemy, attacks=atks, inventory=self.player_inventory, engine=self.engine)
            # tolérance: si l’IO renvoie un Attack tout seul
            if not isinstance(res, tuple):
                return ("attack", res)
            return res
        # fallback: première attaque dispo
        return ("attack", atks[0] if atks else Attack(name="Attaque", base_damage=5, variance=2, cost=0))

    def _select_enemy_attack(self, enemy: Enemy) -> Attack:
        atks = list(enemy.attacks or [])
        if not atks:
            return Attack(name="Coup maladroit", base_damage=4, variance=2, cost=0)
        ai = enemy.behavior_ai
        if ai is not None:
            try:
                return ai.choose(enemy=enemy, player=self.player, attacks=atks, rng=self.rng)
            except Exception:
                pass
        # Fallback au cas où (aléatoire pondéré)
        ws = getattr(enemy, "attack_weights", [1]*len(atks))
        total = sum(ws); r =self.rng.uniform(0, total); acc = 0.0
        for atk, w in zip(atks, ws):
            acc += w
            if r <= acc:
                return atk
        return atks[-1]
    
    def _use_item_in_combat(self, item_id: str) -> CombatResult:
        events: list[CombatEvent] = []
        ctx = CombatContext(attacker=self.player, defender=None, events=events)  # defender None: action utilitaire
        item_events = self.player_inventory.use_consumable(item_id, user=self.player, ctx=ctx)
        if isinstance(item_events, list):
            events.extend(item_events)
        elif item_events:
            events.append(item_events)
        # Utiliser un objet consomme le tour, n'inflige pas de dégâts
        return CombatResult(events=events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False)

    def _apply_attack_effects(self, attacker: Player | Enemy, defender: Player | Enemy, attack: Attack, result: CombatResult):
        """Applique les effets listés sur `attack` si l'attaque a touché.

        - on_hit(ctx) est appelé pour des effets *immédiats* (ex.: dégâts bonus).
        - Si l'effet a une `duration` > 0, on l'enregistre pour des ticks futurs.
        """
        if result.defender_alive:
            effs = getattr(attack, "effects", None)
            if not effs:
                return
            
            # Choix de la cible: par défaut sur le défenseur; si attack.target == "self", sur l'attaquant
            target = attacker if getattr(attack, "target", "enemy") == "self" else defender

            # Contexte d'événements pour le log
            events: list[CombatEvent] = []
            ctx = CombatContext(attacker=attacker, defender=defender, events=events)

            # On applati si besoin
            if not isinstance(effs, list):
                effs = [effs]
            flat: list = []
            for e in effs:
                if isinstance(e, list):
                    flat.extend(e)
                else:
                    flat.append(e)
                    
            for raw in flat:
                e2 = self._instantiate_effect(raw)
                if not e2:
                    continue
                try:
                    self.effects.apply(target, e2, source_name=f"attack:{attack.name}", ctx=ctx, max_stacks=getattr(e2, "max_stack", 1))
                except Exception:
                    try:
                        e2.on_apply(target, ctx)
                    except Exception:
                        pass

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
                res = None
                action = self.io.choose_supply_action(self.player, wallet=self.wallet, offers=offers)
                if action == "REST":
                    res = mgr.do_rest(self.player, hp_pct=REST_HP_PCT, sp_pct=REST_SP_PCT)
                    if res is not None and self.io:
                        self.io.present_events(CombatResult(events=res.events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))
                    break
                elif action == "REPAIR":
                    res = mgr.repair_all_you_can_afford(self.player, price_per_point=REPAIR_COST_PER_POINT)
                    if res is not None and self.io:
                        self.io.present_events(CombatResult(events=res.events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))
                    break
                elif action == "SHOP":
                    stock = self._build_shop_stock(lvl=self.zone.level, zone=self.zone)
                    # 2) afficher le stock (si tu veux une preview rapide)
                    if self.io:
                        if stock["items"]:
                            self.io.present_text("— Boutique (Objets) —")
                            for iid, price, qty in stock["items"]:
                                self.io.present_text(f"  {iid}  x{qty}  — {price} or")
                        if stock["equip"]:
                            self.io.present_text("— Boutique (Équipement) —")
                            for i, (eq, price) in enumerate(stock["equip"], 1):
                                self.io.present_text(f"  [{i}] [{eq.slot}] {eq.name} — {price} or — {eq.get_info()}")

                    # 3) laisser l’IO choisir (implémente une méthode choose_shop_from_stock si tu veux)
                    purchase = None
                    # laisser l’IO sélectionner une offre + quantité
                    if hasattr(self.io, "choose_shop_purchase"):
                        choice = self.io.choose_shop_purchase(offers, wallet=self.wallet)
                        if choice is None:
                            res = None
                        else:
                            offer, qty = choice
                            res = mgr.buy_offer(self.player, offer, qty=qty)
                            if offer.kind == "class_scroll" and res is not None:
                                setattr(self.player, "class_attack_unlocked", True)
                    else:
                        res = None
                    if res is not None and self.io:
                        self.io.present_events(CombatResult(events=res.events, attacker_alive=True, defender_alive=True, damage_dealt=0, was_crit=False))
                    break
                elif action == "INSPECT":
                    if self.io:
                        self.io.present_text(self._player_sheet(None))
                    res = None  # pas d'événement combat
                    continue

                elif action == "EQUIP":
                    # L’IO peut proposer une sélection (slot,index). À défaut, on montre la liste.
                    payload = None
                    if hasattr(self.io, "choose_inventory_equip"):
                        payload = self.io.choose_inventory_equip(self.player, inventory=self.player_inventory)
                        # attendu: {"index": 0} (slot inféré) ou None
                    if not payload:
                        # fallback: on affiche la liste
                        if self.io:
                            self.io.present_text(self._player_sheet(None))
                        res = None
                    else:
                        ok, msg = self.player_inventory.equip_equipment_by_index(self.player, int(payload.get("index",-1)))
                        if self.io:
                            self.io.present_text(("Équipement: " + msg) if ok else ("Échec: " + msg))
                        res = None
                    continue

                elif action == "SELL":
                    # (Optionnel) vente de consommables par ID (ex: "potion_hp_s"), IO choisit item_id + qty
                    payload = None
                    if hasattr(self.io, "choose_sell_items"):
                        payload = self.io.choose_sell_items(self.player_inventory, wallet=self.wallet)
                        # attendu: {"item_id":"potion_hp_s","qty":2} ou None
                    if payload:
                        ok, msg = self._sell_item(payload.get("item_id",""), int(payload.get("qty", 0)))
                        if self.io:
                            self.io.present_text(msg)
                    res = None
                    break

                elif action == "SAVE":
                    ok = save_to_file(self, "save_slot_1.json")
                    if self.io:
                        msg = "Sauvegarde réussie." if ok else "Échec de sauvegarde."
                        self.io.present_text(msg)
                    break
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
                    e = bp.build(level=zone.level)
                    setattr(e, "is_boss", is_boss)
                    return e

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

    def _instantiate_effect(self, raw) -> Effect | None:
        """Normalise un 'raw effect' en instance d'Effect.
        - Effect -> clone
        - dict   -> make_effect(id/duration/potency)
        - str    -> make_effect(id)
        - list   -> non supporté ici, géré à l'appelant (itération)
        """
        try:
            if isinstance(raw, Effect):
                return self._clone_effect_instance(raw)
            if isinstance(raw, dict):
                rid = raw.get("id") or raw.get("name")
                dur = int(raw.get("duration", 0))
                pot = int(raw.get("potency", 0))
                return make_effect(rid, dur, pot)
            if isinstance(raw, str):
                return make_effect(raw, 0, 0)
        except Exception:
            return None
        return None
    
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
    
    def _roll_item_drops(self, enemy: Enemy, is_boss: bool) -> list[tuple[str, int]]:
        """
        Retourne une liste de (item_id, qty) à drop.
        1) Si le blueprint de l'ennemi fournit des drops → on respecte.
        2) Sinon fallback simple: petites/moyennes/grandes potions avec proba selon zone.level.
        """
        drops: list[tuple[str, int]] = []

        # 1) Drops définis sur le blueprint de l'ennemi (optionnel)
        eid = getattr(enemy, "enemy_id", None)
        bp: EnemyBlueprint = self.enemy_blueprints.get(eid) if eid and hasattr(self, "enemy_blueprints") else None
        if bp and isinstance(bp.drops, dict):
            items = list(getattr(bp.drops, "get", lambda k, d=[]: d)("items", [])) if isinstance(bp.drops, dict) else []
            total_w = sum(int(r.get("w", 1)) for r in items) or 0
            if total_w > 0:
                # 1 tirage garanti; boss → 2 tirages
                pulls = 2 if is_boss else 1
                for _ in range(pulls):
                    r = self.rng.uniform(0, total_w)
                    acc = 0
                    chosen = None
                    for row in items:
                        acc += int(row.get("w", 1))
                        if r <= acc:
                            chosen = row; break
                    if chosen:
                        qlo, qhi = (1, 1)
                        q = chosen.get("qty")
                        if isinstance(q, (list, tuple)) and len(q) == 2:
                            qlo, qhi = int(q[0]), int(q[1])
                        qty = max(1, int(self.rng.randint(qlo, qhi)))
                        drops.append((str(chosen.get("id")), qty))
            return drops

        # 2) Fallback global basé sur items.json (aucune config ennemi)
        _IF = (self.item_factories or {})
        available = [iid for iid in _IF.keys()
                     if iid in ("potion_hp_s","potion_sp_s","potion_hp_m","potion_sp_m","potion_hp_l","potion_sp_l")]
        if not available:
            return drops

        lvl = getattr(self.zone, "level", 1)
        # Probabilité de drop brut (au moins un item)
        # ↑ avec le niveau; typiquement 35% + 3% * (lvl-1), borné 20–70%
        p_any = min(0.70, max(0.20, 0.35 + 0.03*(lvl-1)))
        if self.rng.random() > p_any and not is_boss:
            return drops

        # Pondérations par "taille" de potion
        # petites ≫ moyennes ≫ grandes ; augmente légèrement avec lvl
        w_small  = 70 + 2*(lvl-1)   # s
        w_medium = 25 + 1*(lvl-1)   # m
        w_large  = 5 + (lvl//5)     # l
        weights = {
            "potion_hp_s": w_small, "potion_sp_s": w_small,
            "potion_hp_m": w_medium,"potion_sp_m": w_medium,
            "potion_hp_l": w_large, "potion_sp_l": w_large,
        }
        # 1 tirage de base, boss → 2 tirages
        pulls = 2 if is_boss else 1
        for _ in range(pulls):
            total = sum(weights.get(i,1) for i in available)
            r = self.rng.uniform(0, total)
            acc = 0
            choice = None
            for iid in available:
                acc += weights.get(iid,1)
                if r <= acc:
                    choice = iid; break
            if choice:
                # qty: petites 1–2, moyennes 1, grandes 1 (rarement 2 si lvl élevé)
                if choice.endswith("_s"):
                    qty = 1 if self.rng.random() < 0.5 else 2
                elif choice.endswith("_m"):
                    qty = 1
                else:  # _l
                    qty = 2 if lvl >= 10 and self.rng.random() < 0.15 else 1
                drops.append((choice, qty))
        return drops

    def _roll_equipment_drop(self, *, is_boss: bool) -> list:
        """Retourne une liste d'objets Equipment (instances) à ajouter à l'inventaire."""
        banks = (self.weapon_bank, self.armor_bank, self.artifact_bank)
        zone: ZoneType  = getattr(self.zone, "zone_type", None)
        lvl   = getattr(self.zone, "level", 1)
        tier  = max(1, min(5, round((lvl+1)/2)))
        is_forced = False

        # pitié / boss
        streak = getattr(self, "_no_equip_streak", 0)
        if is_boss:
            pulls = 1
            is_forced = True
        else:
            base_p = min(0.40, max(0.08, 0.08 + 0.02*(lvl-1)))
            if streak >= 6:
                is_forced = True
            pulls = 1 if (is_forced or self.rng.random() < base_p) else 0

        drops = []
        for _ in range(pulls):
            pool = []
            for bank in banks:
                for proto in bank:
                    # filtres doux: tier +-1, zones si définies
                    ok_tier = abs(getattr(proto, "tier", tier) - tier) <= 1
                    zs = set(getattr(proto, "zones", []) or [])
                    ok_zone = (not zs) or (zone and zone.name in zs)
                    if ok_tier and ok_zone:
                        pool.append(proto)
            if not pool:
                continue
            proto = self.rng.choice(pool)
            # instancier une COPIE (pas l’objet banque)
            inst = proto.clone() if hasattr(proto, "clone") else type(proto)(**proto.to_ctor_args())
            drops.append(inst)

        # MAJ pitié
        setattr(self, "_no_equip_streak", 0 if drops else streak+1)
        return drops

    def _grant_equipment(self, eq_list: list) -> None:
        inv = self.player_inventory
        added = []
        for e in (eq_list or []):
            try:
                inv.add_equipment(e)
                added.append(f"[{getattr(e,'slot','?')}] {getattr(e,'name','?')}")
            except Exception:
                pass
        if added and self.io:
            self.io.present_text("Butin (équipement): " + ", ".join(added) + ".")

    def _grant_items(self, drops: list[tuple[str, int]]) -> None:
        """Ajoute les items droppés à l'inventaire + feedback IO."""
        if not drops: 
            return
        factories = (self.item_factories or {})
        added: list[str] = []
        inv = self.player_inventory

        for iid, qty in drops:
                fac = factories.get(iid)
                if not fac:
                    continue
                try:
                    inst = fac()
                    inv.add_item(inst, qty)
                    added.append(f"{qty}× {getattr(inst, 'name', iid)}")
                except Exception:
                    pass
        if added and self.io:
            self.io.present_text("Butin: " + ", ".join(added) + ".")

    def _sell_item(self, item_id: str, qty: int) -> tuple[bool, str]:
        """Vend jusqu'à `qty` unités d'un consommable. Prix = 50% du base_price de items.json."""
        if not item_id or qty <= 0:
            return (False, "Vente: item ou quantité invalide.")

        factories = getattr(self, "item_factories", {}) or {}
        fac = factories.get(item_id)
        if not fac:
            return (False, f"Vente: item inconnu '{item_id}'.")
        try:
            sample: Item | Equipment = fac()  # instance pour lire le nom/prix
        except Exception:
            return (False, "Vente: impossible d'instancier l'objet.")

        base_price = int(getattr(sample, "base_price", 0))
        if base_price <= 0:
            return (False, f"Vente: '{sample.name}' n'a pas de valeur.")
        have = self.player_inventory.count(item_id)
        if have <= 0:
            return (False, f"Vente: vous n'avez pas de {sample.name}.")
        take = min(have, int(qty))
        removed = self.player_inventory.remove_item(item_id, take)
        if removed <= 0:
            return (False, "Vente: rien retiré.")

        revenue = int(0.5 * base_price * removed)
        self.wallet.add(revenue)
        return (True, f"Vendu {removed}× {sample.name} pour {revenue} or.")

    def _build_shop_stock(self, *, lvl: int, zone: Zone) -> dict:
        """
        Retourne {"items":[(id,price,qty)], "equip":[(Equipment, price)]}.
        Prix = base_price * coeff (tier/rareté); qty = 1-3 pour consommables.
        """
        factories = getattr(self, "item_factories", {}) or {}
        items = []

        # Items: privilégie ceux dont zones contient la zone courante
        cand = []
        for iid, fac in factories.items():
            try:
                sample = fac()
                zs = set(getattr(sample, "zones", []) or [])
                tier = int(getattr(sample, "tier", 1))
                w = int(getattr(sample, "shop_weight", 1))
                ok_zone = (not zs) or (zone and zone.zone_type.name in zs)
                if ok_zone and abs(tier - round((lvl+1)/2)) <= 1:
                    cand.append((iid, sample, w))
            except Exception:
                continue
        # 4 items max
        for _ in range(min(4, len(cand))):
            total = sum(w for _,_,w in cand)
            r = self.rng.uniform(0, total); acc = 0
            for i,(iid,s,w) in enumerate(cand):
                acc += w
                if r <= acc:
                    price = max(1, int(getattr(s, "base_price", 10) * (1.0 + 0.1*lvl)))
                    qty = 1 if s.stackable is False else self.rng.randint(1, 3)
                    items.append((iid, price, qty))
                    cand.pop(i)  # éviter doublon
                    break

        # Équipements (2 slots max): filtrés par zone/tier
        eqs = []
        bank_all = list(self.weapon_bank) + list(self.armor_bank) + list(self.artifact_bank)
        pool = []
        for proto in bank_all:
            zs = set(getattr(proto, "zones", []) or [])
            ok_zone = (not zs) or (zone and zone.zone_type.name in zs)
            t = int(getattr(proto, "tier", 1))
            if ok_zone and abs(t - round((lvl+1)/2)) <= 1:
                pool.append(proto)
        for _ in range(min(2, len(pool))):
            p = self.rng.choice(pool)
            inst = p.clone() if hasattr(p, "clone") else type(p)(**p.to_ctor_args())
            base = int(getattr(inst, "base_price", 50) or 50)
            # pricing léger : +25% par tier au-dessus de 1
            price = int(base * (1.0 + 0.25*(int(getattr(inst,"tier",1))-1)))
            eqs.append((inst, price))
            pool.remove(p)

        return {"items": items, "equip": eqs}

    def _player_sheet(self, enemy: Enemy | None = None) -> str:
        """Construit un petit résumé: stats, attaques dispo (avec estimation), équipement."""
        lines: list[str] = []
        p: Player = self.player
        lines.append(f"— Fiche de {p.name} —")
        lines.append(f"HP: {p.hp}/{p.max_hp} | SP: {p.sp}/{p.max_sp}")
        lines.append(f"ATK: {p.base_stats.attack} | DEF: {p.base_stats.defense} | LCK: {p.base_stats.luck}")
        lines.append("")

        # Attaques (avec estimation si ennemi fourni)
        atks = self._gather_player_attacks()
        lines.append("Attaques disponibles:")
        if not atks:
            lines.append("  (Aucune)")
        else:
            for a in atks:
                if enemy is not None:
                    lo, hi = self.engine.estimate_damage(p, enemy, a)
                    span = f"{lo}–{hi}"
                else:
                    span = "?"
                desc = getattr(a, "description", "") or ""
                lines.append(f"  • {a.name} (coût SP: {a.cost}) | Dégâts ~ {span} | {desc}")

        lines.append("")
        # Équipement
        eq = p.equipment
        lines.append("Équipement:")
        lines.append(f"  Arme     : {eq.weapon.get_info()}")
        lines.append(f"  Armure   : {eq.armor.get_info()}")
        lines.append(f"  Artefact : {eq.artifact.get_info()}")

        # Inventaire (équipement stocké)
        try:
            stored = self.player_inventory.list_equipment()
            if stored:
                lines.append("")
                lines.append("Équipements en inventaire:")
                for i, e in enumerate(stored):
                    lines.append(f"  [{i}] {e.get_info()}")
        except Exception:
            pass

        return "\n".join(lines)

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
