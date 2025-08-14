from __future__ import annotations
"""Associe un Loadout à une entité sans modifier Player/Entity."""

from weakref import WeakKeyDictionary
from typing import Optional
from core.loadout import Loadout

class LoadoutManager:
    def __init__(self) -> None:
        self._by_entity: "WeakKeyDictionary[object, Loadout]" = WeakKeyDictionary()

    def set(self, entity: object, loadout: Loadout) -> None:
        self._by_entity[entity] = loadout

    def get(self, entity: object) -> Optional[Loadout]:
        return self._by_entity.get(entity)
