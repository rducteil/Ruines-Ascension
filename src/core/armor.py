from __future__ import annotations
"""Armor: bonus plats (DEF), usure quand on encaisse des dégâts."""

from typing import Optional, List, TYPE_CHECKING
from core.equipment import Equipment
from core.resource import Resource

if TYPE_CHECKING:
    from core.entity import Entity
    from core.combat_types import CombatContext


class Armor(Equipment):
    """Armor: bonus plats (DEF), usure quand on encaisse des dégâts."""

    def __init__(self, 
                 name: str, 
                 durability: Resource, 
                 bonus_defense: int = 0, 
                 description: str = "") -> None:
        super().__init__(name=name, durability=durability, description=description)
        self.bonus_defense: int = int(bonus_defense)

    # --- stat bonuses ---
    def apply_bonuses(self, entity: "Entity") -> None:
        entity.base_stats.defense += self.bonus_defense

    def remove_bonuses(self, entity: "Entity") -> None:
        entity.base_stats.defense -= self.bonus_defense

    # --- usure ---
    def on_after_hit(self, ctx: CombatContext, damage_taken: int) -> None:
        if damage_taken > 0:
            self.degrade(1)