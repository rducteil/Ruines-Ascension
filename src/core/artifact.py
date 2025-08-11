from __future__ import annotations

from core.equipment import Equipment
from core.entity import Entity


class Artifact(Equipment):
    """A versatile equippable that applies several flat stat bonuses."""

    def __init__(
        self,
        name: str,
        durability_max: int,
        bonus_attack: int = 0,
        bonus_defense: int = 0,
        bonus_speed: int = 0,
        bonus_luck: int = 0,
        description: str = "",
    ) -> None:
        super().__init__(name=name, durability_max=durability_max, description=description)
        self.bonus_attack = int(bonus_attack)
        self.bonus_defense = int(bonus_defense)
        self.bonus_speed = int(bonus_speed)
        self.bonus_luck = int(bonus_luck)

    # --- stat bonuses lifecycle ---
    def apply_bonuses(self, entity: "Entity") -> None:
        entity.base_stats.attack += self.bonus_attack
        entity.base_stats.defense += self.bonus_defense
        entity.base_stats.speed += self.bonus_speed
        # If your Stats has `luck`, apply it as well
        if hasattr(entity.base_stats, "luck"):
            entity.base_stats.luck += self.bonus_luck

    def remove_bonuses(self, entity: "Entity") -> None:
        entity.base_stats.attack -= self.bonus_attack
        entity.base_stats.defense -= self.bonus_defense
        entity.base_stats.speed -= self.bonus_speed
        if hasattr(entity.base_stats, "luck"):
            entity.base_stats.luck -= self.bonus_luck

    # Example optional hook if you want artifacts to wear over time
    def on_turn_end(self, ctx) -> None:
        # By default: no wear. Uncomment to add slow decay.
        # self.degrade(1)
        pass