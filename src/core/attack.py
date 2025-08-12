from __future__ import annotations
"""Attack: description déclarative (dégâts de base, variance, coût, effets)."""

from dataclasses import dataclass, field
from typing import List, Optional
from core.effects import Effect  # persistant (poison, buff...)

@dataclass
class Attack:
    name: str
    base_damage: int = 0
    variance: int = 0
    cost: int = 0
    crit_multiplier: float = 2.0
    effects: List[Effect] = field(default_factory=list)

    # Modifs de calcul (optionnelles)
    ignore_defense_pct: float = 0.0   # ex: 0.25 => ignore 25% de DEF
    true_damage: int = 0              # dégâts bruts ajoutés après calcul

    # helpers de fabrique si tu veux
    @staticmethod
    def basic(name: str = "Attaque", base_damage: int = 5, variance: int = 2) -> "Attack":
        return Attack(name=name, base_damage=base_damage, variance=variance)
