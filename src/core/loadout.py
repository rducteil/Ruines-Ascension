from __future__ import annotations
"""Loadout d'actions: 3 emplacements (primaire, compétence, utilitaire)."""

from dataclasses import dataclass
from typing import Literal, TypeAlias, TYPE_CHECKING
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from core.attack import Attack
    from core.entity import Entity

Slot: TypeAlias = Literal["primary", "skill", "utility"]
VALID_SLOT = ("primary", "skill", "utility")


@dataclass(slots=True, kw_only=True)
class Loadout:
    primary: Attack      # ex: Attaque de base fiable
    skill: Attack        # ex: Attaque plus complexe ou attaque de classe achetée
    utility: Attack      # ex: Action utilitaire

    def as_list(self) -> list[Attack]:
        return [self.primary, self.skill, self.utility]

    def replace(self, slot: Slot, attack: Attack) -> None:
        if slot not in VALID_SLOT:
            raise ValueError(f"slot invalide {slot}")    
        setattr(self, slot, attack)
        

class LoadoutManager:
    """Associe un Loadout à une entité sans modifier Player/Entity."""
    def __init__(self) -> None:
        self._by_entity: WeakKeyDictionary["Entity", Loadout] = WeakKeyDictionary()

    def set(self, entity: "Entity", loadout: Loadout) -> None:
        self._by_entity[entity] = loadout

    def get(self, entity: "Entity") -> Loadout | None:
        return self._by_entity.get(entity)