from __future__ import annotations

from core.equipment import Equipment
from core.entity import Entity


class Armor(Equipment):
    """An armor piece that grants a flat defense bonus."""

    def __init__(self, name: str, durability_max: int, bonus_defense: int = 0, description: str = "") -> None:
        super().__init__(name=name, durability_max=durability_max, description=description)
        self.bonus_defense: int = int(bonus_defense)

    # --- stat bonuses lifecycle ---
    def apply_bonuses(self, entity: "Entity") -> None:
        entity.base_stats.defense += self.bonus_defense

    def remove_bonuses(self, entity: "Entity") -> None:
        entity.base_stats.defense -= self.bonus_defense

    # --- hooks called by the combat engine ---
    def on_after_hit(self, ctx, damage_taken: int) -> None:
        """Called by the combat engine after the holder takes damage.
        Wear at least 1, plus 1 per 10 damage (example formula).
        """
        # TODO: Adjust wear formula to your balance (e.g., proportional to raw vs. mitigated dmg)
        wear = max(1, damage_taken // 10)
        self.degrade(wear)