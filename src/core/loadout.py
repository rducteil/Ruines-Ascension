from __future__ import annotations
"""Loadout d'actions: 3 emplacements (primaire, compétence, utilitaire)."""

from dataclasses import dataclass
from typing import Iterable, Optional
from weakref import WeakKeyDictionary
from core.attack import Attack

@dataclass
class Loadout:
    primary: Attack      # ex: "Frapper" (fiable)
    skill: Attack        # ex: "Brise-garde" ou attaque de classe achetée
    utility: Attack      # ex: "Charge", "Garde", "Marque"

    def as_list(self) -> list[Attack]:
        return [self.primary, self.skill, self.utility]

    def replace(self, slot: str, attack: Attack) -> None:
        if slot not in ("primary", "skill", "utility"):
            raise ValueError("slot must be 'primary' | 'skill' | 'utility'")
        setattr(self, slot, attack)

class LoadoutManager:
    """Associe un Loadout à une entité sans modifier Player/Entity."""
    def __init__(self) -> None:
        self._by_entity: "WeakKeyDictionary[object, Loadout]" = WeakKeyDictionary()

    def set(self, entity: object, loadout: Loadout) -> None:
        self._by_entity[entity] = loadout

    def get(self, entity: object) -> Optional[Loadout]:
        return self._by_entity.get(entity)