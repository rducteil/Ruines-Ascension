from __future__ import annotations
from typing import Optional, List

from core.equipment import Equipment
from core.attack import Attack
from core.entity import Entity

class Weapon(Equipment):
    """A weapon that grants a flat attack bonus and (optionally) special attacks."""

    def __init__(self,name: str, durability_max: int, bonus_attack: int = 0, special_attacks: Optional[List[Attack]] = None, description: str = ""):
        super().__init__(name=name, durability_max=durability_max, description=description)
        self.bonus_attack: int = int(bonus_attack)
        self.special_attacks: List[Attack] = list(special_attacks or [])

    # --- stat bonuses lifecycle ---
    def apply_bonuses(self, entity: "Entity") -> None:
        """Apply the weapon's stat bonuses to the holder."""
        entity.base_stats.attack += self.bonus_attack

    def remove_bonuses(self, entity: "Entity") -> None:
        """Remove the weapon's stat bonuses from the holder."""
        entity.base_stats.attack -= self.bonus_attack

    # --- hooks called by the combat engine ---
    def on_after_attack(self, ctx) -> None:
        """Called by the combat engine after the holder performs an attack.
        The weapon degrades by 1 on each use (tune as needed).
        """
        # TODO: Tune wear logic (e.g., more wear on heavy attacks / on crit)
        self.degrade(1)

    # --- convenience ---
    def get_available_attacks(self) -> List[Attack]:
        """Attacks granted by this weapon (usable even if the weapon is broken)."""
        return self.special_attacks