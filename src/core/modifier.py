from __future__ import annotations
"""Modifs: 
- ResourceModifier (HP/SP max: flat + %)
- StatPercentMod (ATK/DEF % appliqués à la volée par le moteur)
"""

from dataclasses import dataclass

@dataclass
class ResourceModifier:
    hp_max_flat: int = 0
    hp_max_pct: float = 0.0
    sp_max_flat: int = 0
    sp_max_pct: float = 0.0
    
@dataclass
class StatPercentMod:
    attack_pct: float = 0.0
    defense_pct: float = 0.0
    luck_pct: float = 0.0