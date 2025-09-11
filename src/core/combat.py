from __future__ import annotations
"""Moteur de combat (agnostique de l'I/O). Gère SP, dégâts, crit, usure."""

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
import random
from core.utils  import clamp
from effects import StatPercentMod

if TYPE_CHECKING:
    from core.attack import Attack
    from core.entity import Entity
    from core.equipment import Weapon, Armor

# ---- Protocols facultatifs (pour aider le typage sans import circulaire) ----

@dataclass
class CombatEvent:
    """Un message d'événement + tag et data optionnelles pour l'UI."""
    text: str
    tag: str | None = None
    data: dict[str, Any] | None = None

@dataclass
class CombatResult:
    """Résultat d'une résolution d'attaque (un tour)."""
    events: list[CombatEvent]
    attacker_alive: bool
    defender_alive: bool
    damage_dealt: int
    was_crit: bool

@dataclass
class CombatContext:
    """Contexte minimal passé aux hooks d'équipement/effets."""
    attacker: Entity
    defender: Entity
    events: list[CombatEvent]
    damage_dealt: int = 0
    was_crit: bool = False

# ---- Moteur ----

class CombatEngine:
    """Résout une attaque: coût SP, dégâts, critique, usure, événements."""

    def __init__(
            self, 
            *, 
            seed: int | None = None, 
            _base_crit_mult: float = 2.0
            ):
        self.rng = random.Random(seed)
        self._base_crit_mult = float(_base_crit_mult)


    def resolve_turn(self, attacker: Entity, defender: Entity, attack: Attack) -> CombatResult:
        events: list[CombatEvent] = []
        ctx = CombatContext(attacker=attacker, defender=defender, events=events)

        # 1) Coût en SP (si non payé -> pas d'attaque)
        cost = attack.cost
        if cost and not attacker.spend_sp(cost):
            events.append(CombatEvent(
                text=f"{attacker.name} n'a pas assez d'endurance pour {attack.name}.",
                tag="not_enough_sp",
                data={"cost": cost},
            ))
            return CombatResult(events, attacker_alive=attacker.hp > 0, defender_alive=defender.hp > 0,
                                damage_dealt=0, was_crit=False)

        # 2) Jet de variance & calcul des stats effectives (plats + %)
        base_damage = int(attack.base_damage)
        variance = int(attack.variance)
        delta = self.rng.randint(-variance, variance) if variance > 0 else 0

        eff_atk = self._effective_attack(attacker)
        eff_def = self._effective_defense(defender)
        eff_def = int(round(eff_def * (1.0 - attack.ignore_defense_pct)))

        raw = max(0, base_damage + delta + eff_atk - eff_def)
        raw += attack.true_damage

        # 3) Critique éventuel (basé sur luck)
        was_crit = self._roll_crit(attacker.base_stats.luck)
        if was_crit and raw > 0:
            raw = int(round(raw * self._crit_multiplier(attacker, attack)))

        # 4) Application des dégâts
        dealt = defender.take_damage(raw)
        ctx.damage_dealt = dealt
        ctx.was_crit = was_crit

        if dealt > 0:
            msg = f"{attacker.name} utilise {attack.name} et inflige {dealt} PV."
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

    def _effective_attack(self, entity: Entity) -> int:
        """Attack effective = plats (déjà dans base_stats) * (1 + somme %)."""
        base = int(entity.base_stats.attack)
        pct = self._gather_pct(entity, which="attack")
        return int(round(base * (1.0 + pct)))

    def _effective_defense(self, entity: Entity) -> int:
        base = int(entity.base_stats.defense)
        pct = self._gather_pct(entity, which="defense")
        return int(round(base * (1.0 + pct)))

    def _gather_pct(self, entity: Entity, which: str) -> float:
        art = getattr(entity, "artifact", None)
        if not art or not hasattr(art, "stat_percent_mod"):
            return 0.0
        mod : StatPercentMod = art.stat_percent_mod()
        return float(getattr(mod, f"{which}_pct", 0.0))

    # ---------- Critique ----------

    def _roll_crit(self, luck: int) -> bool:
        """Renvoie True si critique (formule configurable)."""
        p = clamp(float(self._crit_func(int(luck))), 0.0, 1.0)
        return self.rng.random() < p

    def _crit_func(self, luck: int) -> float:
        return (1.0 - (0.98 ** max(0, luck))) / 0.8673804

    def _crit_multiplier(self, entity: Entity, attack: Attack) -> float:
        """x2 par défaut, surcharge possible par l'attaque ou l'équipement."""
        mult = float(getattr(attack, "crit_multiplier", self._base_crit_mult))
        return max(1.0, mult)

    # ---------- Usure ----------

    def _wear_after_attack(self, attacker: Entity, ctx: CombatContext, events: list[CombatEvent]) -> None:
        weapon: Weapon = getattr(attacker, "weapon", None)
        if weapon and hasattr(weapon, "on_after_attack"):
            was_broken = getattr(weapon, "is_broken", lambda: False)()
            weapon.on_after_attack(ctx)
            now_broken = getattr(weapon, "is_broken", lambda: False)()
            if not was_broken and now_broken:
                events.append(CombatEvent(text=f"L'arme de {attacker.name} se casse !", tag="weapon_broken"))

    def _wear_after_hit(self, defender: Entity, ctx: CombatContext, events: list[CombatEvent]) -> None:
        armor: Armor = getattr(defender, "armor", None)
        if armor and hasattr(armor, "on_after_hit"):
            was_broken = getattr(armor, "is_broken", lambda: False)()
            armor.on_after_hit(ctx, damage_taken=ctx.damage_dealt)
            now_broken = getattr(armor, "is_broken", lambda: False)()
            if not was_broken and now_broken:
                events.append(CombatEvent(text=f"L'armure de {defender.name} se brise !", tag="armor_broken"))