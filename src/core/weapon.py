from __future__ import annotations
"""Weapon: bonus plats (ATK), usure à l’usage et attaques spéciales optionelles."""

from typing import Optional, List, TYPE_CHECKING
from core.equipment import Equipment
from core.resource import Resource

if TYPE_CHECKING:
    from core.entity import Entity
    from core.attack import Attack
    from core.combat_types import CombatContext

class Weapon(Equipment):
    """Weapon: bonus plats (ATK), usure à l’usage et attaques spéciales optionelles."""

    def __init__(self, 
                 name: str, 
                 durability_max: int | Resource, 
                 bonus_attack: int = 0, 
                 special_attacks: Optional[List[Attack]] = None, 
                 description: str = ""):
        if isinstance(durability_max, Resource):
            dur = durability_max
        else:
            dur = Resource(current=durability_max, maximum=durability_max)
        super().__init__(name=name, durability=dur, description=description)
        self.bonus_attack: int = int(bonus_attack)
        self.special_attacks: List[Attack] = list(special_attacks or [])

    def get_available_attacks(self) -> List[Attack]:
        """Attaques spéciales offertes par l'arme (optionnel)."""
        return list(self.special_attacks)

    # --- stat bonuses ---
    def apply_bonuses(self, entity: "Entity") -> None:
        """Apply the weapon's stat bonuses to the holder."""
        entity.base_stats.attack += self.bonus_attack

    def remove_bonuses(self, entity: "Entity") -> None:
        """Remove the weapon's stat bonuses from the holder."""
        entity.base_stats.attack -= self.bonus_attack

    # --- usure ---
    def on_after_attack(self, ctx: "CombatContext") -> None:
        '''Hook appelé par le moteur après l'attaque du porteur'''
        self.degrade(1)

    