from __future__ import annotations
"""Effets persistants (poison, buffs). Sans I/O, hooks on_hit / on_turn_end."""

from dataclasses import dataclass
from typing import Optional, List, TYPE_CHECKING
from core.combat import CombatContext, CombatEvent
if TYPE_CHECKING:
    from core.entity import Entity


class Effect:
    """Effet persistant appliqué sur une entité (durée en tours)."""
    def __init__(self, 
                 name: str, 
                 duration: int, 
                 potency: int) -> None:
        self.name = name
        self.duration = int(duration)
        self.potency = int(potency)

    # Appliqué au moment où l'attaque TOUCHE (ex.: poser un poison sur la cible)
    def on_hit(self, ctx: CombatContext) -> None:
        pass

    # Appelé à la FIN de chaque tour (pour chaque entité qui a l'effet)
    def on_turn_end(self, ctx: CombatContext) -> None:
        pass

    def is_expired(self) -> bool:
        return self.duration <= 0

    def tick(self) -> None:
        """Diminue la durée (à appeler en fin de tour côté boucle de jeu)."""
        self.duration -= 1

# --- Liste d'effets ---

class PoisonEffect(Effect):
    """Inflige `potency` dégâts à la fin du tour tant que l'effet est actif."""
    def on_turn_end(self, ctx: CombatContext) -> None:
        if self.is_expired():
            return
        taken = ctx.defender.take_damage(self.potency)
        ctx.events.append(type("CE", (), {})(
            text=f"{ctx.defender.name} subit {taken} dégâts de poison.",
            tag="poison_tick", data={"amount": taken}
        ))
        self.tick()

class AttackBuffEffect(Effect):
    """Buff temporaire sur l'ATTAQUANT : +potency ATTACK pendant `duration` tours."""
    def on_apply(self, target: Entity, ctx: CombatContext):
        target.base_stats.attack += self.potency
        ctx.events.append(CombatEvent(f"{target.name} gagne +{self.potency} ATK", tag="base_attack"))
    def on_hit(self, ctx: CombatContext) -> None:
        # Appliquer immédiatement le buff côté attaquant (exemple plat)
        ctx.attacker.base_stats.attack += self.potency
        ctx.events.append(type("CE", (), {})(
            text=f"{ctx.attacker.name} est galvanisé (+{self.potency} ATK).",
            tag="buff_attack", data={"amount": self.potency}
        ))
    def on_expire(self, target: Entity, ctx: CombatContext):
        target.base_stats.attack -= self.potency
        ctx.events.append(CombatEvent(f"Le buff d'attaque sur {target.name} expire.", tag="buff_expire"))
