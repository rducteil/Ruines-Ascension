from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable, Protocol
import random
from core.entity import Entity

# ---- Protocols facultatifs (pour aider le typage sans import circulaire) ----

class StatPercentMod(Protocol):
    attack_pct: float
    defense_pct: float

class HasStatPercentMod(Protocol):
    def stat_percent_mod(self) -> StatPercentMod: ...

class AttackLike(Protocol):
    name: str
    base_damage: int
    variance: int
    cost: int
    # optionnel
    crit_multiplier: float

# ---- Événements retournés par le moteur ----

@dataclass
class CombatEvent:
    """Un message d'événement + tag et data optionnelles pour l'UI."""
    text: str
    tag: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@dataclass
class CombatResult:
    """Résultat d'une résolution d'attaque (un tour)."""
    events: List[CombatEvent]
    attacker_alive: bool
    defender_alive: bool
    damage_dealt: int
    was_crit: bool

@dataclass
class CombatContext:
    """Contexte minimal passé aux hooks d'équipement/effets."""
    attacker: "Entity"
    defender: "Entity"
    events: List[CombatEvent]
    damage_dealt: int = 0
    was_crit: bool = False


# ---- Moteur ----

class CombatEngine:
    """Résout une attaque: coût SP, dégâts, critique, usure, événements."""

    def __init__(
        self,
        *,
        seed: Optional[int] = None,
        crit_chance_from_luck: Optional[Callable[[int], float]] = None,
        base_crit_multiplier: float = 2.0,  # règle projet: x2 par défaut
    ) -> None:
        self.rng = random.Random(seed)
        self._crit_func = crit_chance_from_luck or self._default_crit_from_luck
        self._base_crit_mult = float(base_crit_multiplier)

    # TODO: brancher ici effets de statut, esquive/parade si tu en ajoutes

    def resolve_turn(self, attacker: "Entity", defender: "Entity", attack: AttackLike) -> CombatResult:
        events: List[CombatEvent] = []
        ctx = CombatContext(attacker=attacker, defender=defender, events=events)

        # 1) Coût en SP (si non payé -> pas d'attaque)
        cost = getattr(attack, "cost", 0) or getattr(attack, "stamina_cost", 0)
        if cost and not attacker.spend_sp(cost):
            events.append(CombatEvent(
                text=f"{attacker.name} n'a pas assez d'endurance pour {getattr(attack, 'name', 'cette attaque')}.",
                tag="not_enough_sp",
                data={"cost": cost},
            ))
            return CombatResult(events, attacker_alive=attacker.hp > 0, defender_alive=defender.hp > 0,
                                damage_dealt=0, was_crit=False)

        # 2) Jet de variance & calcul des stats effectives (plats + %)
        base_damage = int(getattr(attack, "base_damage", 0))
        variance = int(getattr(attack, "variance", 0))
        delta = self.rng.randint(-variance, variance) if variance > 0 else 0

        eff_atk = self._effective_attack(attacker)
        eff_def = self._effective_defense(defender)

        raw = max(0, base_damage + delta + eff_atk - eff_def)

        # 3) Critique éventuel (basé sur luck)
        was_crit = self._roll_crit(attacker.base_stats.luck)
        if was_crit and raw > 0:
            raw = int(round(raw * self._crit_multiplier(attacker, attack)))

        # 4) Application des dégâts
        dealt = defender.take_damage(raw)
        ctx.damage_dealt = dealt
        ctx.was_crit = was_crit

        if dealt > 0:
            msg = f"{attacker.name} utilise {getattr(attack, 'name', 'une attaque')} et inflige {dealt} PV."
            if was_crit:
                msg += " (Coup critique !)"
            events.append(CombatEvent(text=msg, tag="damage", data={"amount": dealt, "crit": was_crit}))
        else:
            events.append(CombatEvent(
                text=f"{attacker.name} n'inflige aucun dégât.",
                tag="no_damage",
                data={"crit": was_crit}
            ))

        # 5) Usure d'équipement (après l'action)
        self._wear_after_attack(attacker, ctx, events)
        if dealt > 0:
            self._wear_after_hit(defender, ctx, events)

        # 6) États de vie
        return CombatResult(
            events=events,
            attacker_alive=attacker.hp > 0,
            defender_alive=defender.hp > 0,
            damage_dealt=dealt,
            was_crit=was_crit,
        )

    # ---------- Helpers calculs ----------

    def _effective_attack(self, entity: "Entity") -> int:
        """Attack effective = plats (déjà dans base_stats) * (1 + somme %)."""
        base = int(entity.base_stats.attack)
        pct = self._gather_pct(entity, which="attack")
        return int(round(base * (1.0 + pct)))

    def _effective_defense(self, entity: "Entity") -> int:
        base = int(entity.base_stats.defense)
        pct = self._gather_pct(entity, which="defense")
        return int(round(base * (1.0 + pct)))

    def _gather_pct(self, entity: "Entity", which: str) -> float:
        """Additionne les pourcentages fournis par les items équipés (ordre-indépendant)."""
        total = 0.0
        for slot in ("weapon", "armor", "artifact"):
            item = getattr(entity, slot, None)
            if item is None:
                continue
            # Désactivé si cassé: Equipment gère bonuses_active/is_broken
            if hasattr(item, "stat_percent_mod"):
                mod = item.stat_percent_mod()
                if mod is None:
                    continue
                if which == "attack" and hasattr(mod, "attack_pct"):
                    total += float(mod.attack_pct)
                elif which == "defense" and hasattr(mod, "defense_pct"):
                    total += float(mod.defense_pct)
        return total

    # ---------- Critique ----------

    def _roll_crit(self, luck: int) -> bool:
        """Renvoie True si critique (formule configurable)."""
        p = max(0.0, min(1.0, float(self._crit_func(int(luck)))))
        return self.rng.random() < p

    def _default_crit_from_luck(self, luck: int) -> float:
        """Formule par défaut (décroissance géométrique) : p = 1 - 0.99**luck.
        - 0 luck  -> 0%
        - 10 luck -> ~9.6%
        - 50 luck -> ~39.5%
        Remplace-la en passant crit_chance_from_luck=... au constructeur si tu veux autre chose.
        """
        return 1.0 - (0.99 ** max(0, luck))

    def _crit_multiplier(self, entity: "Entity", attack: AttackLike) -> float:
        """x2 par défaut, surcharge possible par l'attaque ou l'équipement."""
        mult = float(getattr(attack, "crit_multiplier", self._base_crit_mult))
        # Option: bonus d'équipement (addition simple)
        for slot in ("weapon", "armor", "artifact"):
            item = getattr(entity, slot, None)
            if item and hasattr(item, "crit_mult_bonus"):
                mult += float(item.crit_mult_bonus())
        return max(1.0, mult)

    # ---------- Usure ----------

    def _wear_after_attack(self, attacker: "Entity", ctx: CombatContext, events: List[CombatEvent]) -> None:
        weapon = getattr(attacker, "weapon", None)
        if weapon and hasattr(weapon, "on_after_attack"):
            was_broken = getattr(weapon, "is_broken", lambda: False)()
            weapon.on_after_attack(ctx)
            now_broken = getattr(weapon, "is_broken", lambda: False)()
            if not was_broken and now_broken:
                events.append(CombatEvent(text=f"L'arme de {attacker.name} se casse !", tag="weapon_broken"))

    def _wear_after_hit(self, defender: "Entity", ctx: CombatContext, events: List[CombatEvent]) -> None:
        armor = getattr(defender, "armor", None)
        if armor and hasattr(armor, "on_after_hit"):
            was_broken = getattr(armor, "is_broken", lambda: False)()
            armor.on_after_hit(ctx, damage_taken=ctx.damage_dealt)
            now_broken = getattr(armor, "is_broken", lambda: False)()
            if not was_broken and now_broken:
                events.append(CombatEvent(text=f"L'armure de {defender.name} se brise !", tag="armor_broken"))