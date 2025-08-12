from __future__ import annotations
"""Artifact: donne uniquement des bonus en pourcentage (ATK/DEF…)."""

from typing import TYPE_CHECKING
from core.equipment import Equipment
from modifier import StatPercentMod
if TYPE_CHECKING:
    from core.entity import Entity



class Artifact(Equipment):
    """A versatile equippable that applies several flat stat bonuses."""

    def __init__(self, 
                 name: str, 
                 durability_max: int, 
                 atk_pct=0.0, 
                 def_pct=0.0, 
                 lck_pct=0.0, 
                 description: str = ""):
        super().__init__(name=name, durability_max=durability_max, description=description)
        self.atk_pct = int(atk_pct)
        self.def_pct = int(def_pct)
        self.lck_pct = int(lck_pct)

    # --- stat bonuses lifecycle ---
    def apply_bonuses(self, entity: "Entity"):
        pass

    def remove_bonuses(self, entity: "Entity"):
        pass
    
    def stat_percent_mod(self) -> StatPercentMod:
        if self.is_broken() or not self.bonuses_active:
            return StatPercentMod
        return StatPercentMod(
            attack_pct=self.atk_pct,
            defense_pct=self.def_pct,
            luck_pct=self.lck_pct
        )

    def on_turn_end(self, ctx) -> None:
        pass