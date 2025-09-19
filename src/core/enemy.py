from __future__ import annotations
"""Enemy : entité contrôlée par l'IA.

- Hérite de Entity.
- Peut porter un tag/behavior simple (aggressif, défensif, etc.).
- Aucun I/O, hooks d’IA appelés par le contrôleur de jeu.
"""

from typing import TYPE_CHECKING
from math import inf

from core.entity import Entity
from core.stats import Stats
from core.equipment import Weapon, Armor, Artifact
from core.equipment_set import EquipmentSet

if TYPE_CHECKING:
    pass


class Enemy(Entity):
    """
        Non-player combatant with optional behavior tag.
        init: name, base_stats, base_hp_max, base_sp_max, behavior    
    """

    def __init__(self, 
                 name: str, 
                 base_stats: Stats, 
                 base_hp_max: int, 
                 base_sp_max: int = 0, 
                 behavior: str | None = None):
        super().__init__(name=name, base_stats=base_stats, base_hp_max=base_hp_max, base_sp_max=base_sp_max)
        self.behavior: str | None = behavior  # e.g., "aggressif", "défensif"
        self.effect: object | None = None
        self.equipment: EquipmentSet = EquipmentSet(
            weapon=Weapon(name="Membre", durability_max=inf),
            armor=Armor(name="Chair", durability_max=inf),
            artifact=Artifact(name="Malice", durability_max=inf)
        )

    def choose_action(self) -> str:
        """Very simple placeholder AI.
        TODO: Replace with a proper action selection (weights, cooldowns, states).
        """
        return "basic_attack"
    
    def __str__(self):
        return f"{self.name}\n" + super().__str__()

    # Factory helpers for tests/demo
    @staticmethod
    def training_dummy() -> Enemy:
        from core.stats import Stats
        return Enemy(name="Poupée d'entraînement", base_stats=Stats(attack=1, defense=0, speed=0), base_hp_max=30)
    
