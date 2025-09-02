from __future__ import annotations
"""Effets persistants (poison, buffs) — sans I/O.

- Les effets sont *déclaratifs*. Le GameLoop/EffectManager orchestre leur durée.
- On évite toute dépendance forte : uniquement des types neutres (CombatContext/Event).
- Convention d'appel :
  * on_apply(target, ctx)  -> appelé quand l'effet est appliqué à une entité
  * on_hit(ctx)            -> appelé si l'effet est attaché à une attaque qui touche
  * on_turn_end(ctx)       -> appelé à la fin du tour du *porteur* de l'effet
  * on_expire(target, ctx) -> appelé quand l'effet expire (durée atteinte)
"""

from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

from core.combat import CombatContext, CombatEvent

if TYPE_CHECKING:
    from core.entity import Entity

TargetSide = Literal["self", "target"]

@dataclass
class ResourceModifier:
    """Modifs: HP/SP max: flat + %"""
    hp_max_flat: int = 0
    hp_max_pct: float = 0.0
    sp_max_flat: int = 0
    sp_max_pct: float = 0.0
    
@dataclass
class StatPercentMod:
    """Modifs: ATK/DEF % appliqués par le moteur"""
    attack_pct: float = 0.0
    defense_pct: float = 0.0
    luck_pct: float = 0.0

@dataclass
class Effect:
    """
        Base d'effet persistant.
        Args: name, duration, potency, target
    """
    name: str
    duration: int
    potency: int
    target: TargetSide = "target"

    # --- Hooks overridables ---
    def on_hit(self, ctx: CombatContext) -> None:
        pass

    def on_apply(self, target: Entity, ctx: CombatContext):
        '''Appelé lors de l'enregistrement sur "target"'''
        pass

    def on_turn_end(self, ctx: CombatContext) -> None:
        '''Agit à la fin du tour du porteur'''
        pass

    def is_expired(self) -> bool:
        return self.duration <= 0
    
    def on_expire(self, target: Entity, ctx: CombatContext):
        '''Retire les effets réversibles'''
        pass

    # --- Utilitaire ---
    def tick(self) -> None:
        self.duration -= 1

# --- Liste d'effets ---

class PoisonEffect(Effect):
    def __init__(self, name: str, duration: int, potency: int):
        super().__init__(name=name, duration=duration, potency=potency, target="target")
    
    def on_turn_end(self, ctx: CombatContext) -> None:
        if self.is_expired():
            return
        
        # Ici : ctx.attacker == porteur (cible qui a l'effet)
        taken = ctx.attacker.take_damage(self.potency)
        ctx.events.append(CombatEvent(
            text=f"{ctx.attacker.name} subit {taken} dégats de poison.",
            tag="poison_tick",
            data={"amount": taken}
        ))
        self.tick()

class AttackBuffEffect(Effect):
    def __init__(self, name: str, duration: int, potency: int):
        super().__init__(name=name, duration=duration, potency=potency, target="self")

    def on_apply(self, target, ctx: CombatContext) -> None:
        target.base_stats.attack += self.potency
        ctx.events.append(CombatEvent(
            text=f"{target.name} gagne +{self.potency} ATK.",
            tag="buff_attack_apply",
            data={"amount": self.potency},
        ))

    def on_expire(self, target, ctx: CombatContext) -> None:
        target.base_stats.attack -= self.potency
        ctx.events.append(CombatEvent(
            text=f"Le buff d'attaque de {target.name} expire.",
            tag="buff_attack_expire",
        ))
    
class DefenseBuffEffect(Effect):
    def __init__(self, name: str, duration: int, potency: int):
        super().__init__(name=name, duration=duration, potency=potency, target="self")

    def on_apply(self, target, ctx: CombatContext) -> None:
        target.base_stats.defense += self.potency
        ctx.events.append(CombatEvent(
            text=f"{target.name} gagne +{self.potency} DEF.",
            tag="buff_defense_apply",
            data={"amount": self.potency},
        ))

    def on_expire(self, target, ctx: CombatContext) -> None:
        target.base_stats.defense -= self.potency
        ctx.events.append(CombatEvent(
            text=f"Le buff de défense de {target.name} expire.",
            tag="buff_defense_expire",
        ))

class LuckBuffEffect(Effect):
    def __init__(self, name: str, duration: int, potency: int):
        super().__init__(name=name, duration=duration, potency=potency, target="self")

    def on_apply(self, target, ctx: CombatContext) -> None:
        target.base_stats.luck += self.potency
        ctx.events.append(CombatEvent(
            text=f"{target.name} gagne +{self.potency} LCK.",
            tag="buff_luck_apply",
            data={"amount": self.potency},
        ))

    def on_expire(self, target, ctx: CombatContext) -> None:
        target.base_stats.luck -= self.potency
        ctx.events.append(CombatEvent(
            text=f"Le buff de chance de {target.name} expire.",
            tag="buff_luck_expire",
        ))

