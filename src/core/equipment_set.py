"""Regroupe l'arme, l'armure et l'artefact équipés d'une entité."""

from __future__ import annotations
from typing import Literal
from math import inf

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

NO_EQUIP = EquipmentSet(
    weapon=Weapon(name="Main nue", durability_max=1, bonus_attack=0, description="Arme de dernier recourt"),
    armor=Armor(name="Corp nu", durability_max=1, bonus_defense=0, description="Armure de dernier recourt"),
    artifact=Artifact(name="Confiance en soi", durability_max=inf, atk_pct=0.0, def_pct=0.0, lck_pct=0.01, description="Providence de dernier recourt")
)