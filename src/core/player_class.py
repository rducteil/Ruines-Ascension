from __future__ import annotations
"""Définitions des classes de joueur + registre CLASSES."""

from dataclasses import dataclass
from typing import Optional

from core.stats import Stats
from core.attack import Attack
from core.entity import Entity


@dataclass
class PlayerClass:
    """Defines starting bonuses and a signature class attack."""
    name: str
    bonus_stats: Stats = Stats(attack=0, defense=0, luck=0)
    bonus_hp_max: int = 0
    bonus_sp_max: int = 0
    class_attack: Optional[Attack] = None

    def apply_to(self, player: Entity) -> None:
        """Apply bonuses to a freshly created player (mutates stats/resources)."""
        # Stats bonus (flat)
        player.base_stats.attack += self.bonus_stats.attack
        player.base_stats.defense += self.bonus_stats.defense
        player.base_stats.luck += self.bonus_stats.luck

        # Resource maxima (flat). Preserve ratio of current/maximum on change
        player.hp_res.set_maximum(player.hp_res.maximum + self.bonus_hp_max, preserve_ratio=True)
        player.sp_res.set_maximum(player.sp_res.maximum + self.bonus_sp_max, preserve_ratio=True)

        # Optional: store signature attack on the player (UI will expose it)
        if self.class_attack is not None:
            setattr(player, "class_attack", self.class_attack)

