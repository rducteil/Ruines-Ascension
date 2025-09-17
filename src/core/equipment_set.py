"""Regroupe l'arme, l'armure et l'artefact équipés d'une entité."""

from __future__ import annotations
from typing import Literal

from core.equipment import Weapon, Armor, Artifact


Slot = Literal["weapon", "armor", "artifact"]

class EquipmentSet:
    def __init__(self, weapon: Weapon, armor: Armor, artifact: Artifact) -> None:
        self.weapon = weapon
        self.armor = armor
        self.artifact = artifact

    def get(self, slot: Slot):
        return getattr(self, slot)

    def replace(self, slot: Slot, item) -> None:
        setattr(self, slot, item)
