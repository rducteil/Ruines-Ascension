from __future__ import annotations
"""Définitions des classes de joueur + registre CLASSES."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.stats import Stats
from core.equipment_set import EquipmentSet

if TYPE_CHECKING:
    from core.player import Player
    from core.attack import Attack


@dataclass
class PlayerClass:
    """
        Définie bonus de départs et l'attaque de classe (compétence).
        args: name, bonus_stats, bonus_hp_max, bonus_sp_max, class_attack    
    """
    name: str
    bonus_stats: Stats = field(default_factory=lambda: Stats(attack=0, defense=0, luck=0))
    bonus_hp_max: int = 0
    bonus_sp_max: int = 0
    class_attack: Attack | None = None
    class_base_equip: EquipmentSet = EquipmentSet(weapon=None, armor=None, artifact=None)

    def apply_to(self, player: "Player") -> None:
        """Applique les bonus au joueur crée (change les stats et ressources)."""
        # Stats bonus (flat)
        player.base_stats.attack += self.bonus_stats.attack
        player.base_stats.defense += self.bonus_stats.defense
        player.base_stats.luck += self.bonus_stats.luck

        # Resource maxima (flat). Garde le ratio
        player.hp_res.set_maximum(player.hp_res.maximum + self.bonus_hp_max, preserve_ratio=True)
        player.sp_res.set_maximum(player.sp_res.maximum + self.bonus_sp_max, preserve_ratio=True)

        # Equip de l'équipement de base
        player.equipment.replace("weapon", self.class_base_equip.weapon)
        player.equipment.replace("armot", self.class_base_equip.armor)
        player.equipment.replace("artifact", self.class_base_equip.artifact)

        # Si présent, ajoute l'attaque de classe au joueur (pour l'UI)
        if self.class_attack is not None:
            setattr(player, "class_attack", self.class_attack)
