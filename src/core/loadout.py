from __future__ import annotations
"""Loadout d'actions: 3 emplacements (primaire, compétence, utilitaire)."""

from dataclasses import dataclass
from typing import Iterable
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

