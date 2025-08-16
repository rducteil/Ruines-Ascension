from __future__ import annotations
"""Player : entité jouable.

- Hérite de Entity.
- Gère les slots d'équipement (weapon/armor/artifact) via equip/unequip.
- Applique les bonus de PlayerClass à l'init.
- Aucune I/O ici (compatible console & PyGame).
"""

from typing import Optional, TYPE_CHECKING, Literal

from core.entity import Entity
from core.stats import Stats
from core.player_class import PlayerClass, CLASSES as CLASS_REG



if TYPE_CHECKING:
    from core.equipment import Equipment
    from core.weapon import Weapon
    from core.armor import Armor
    from core.artifact import Artifact
    from core.attack import Attack

class Player(Entity):
    def __init__(self, 
                 name: str, 
                 player_class_key: str, 
                 base_stats: Stats, 
                 base_hp_max: int,
                 base_sp_max: int) :
        super().__init__(name=name, base_stats=base_stats, base_hp_max=base_hp_max, base_sp_max=base_sp_max)

        # Equipment slots (optional at start)
        self.weapon: Optional[Equipment] = None
        self.armor: Optional[Equipment] = None
        self.artifact: Optional[Equipment] = None

        # Apply class bonuses (stats + resources) if provided
        self.player_class_key = (player_class_key or "").strip().lower()
        self.player_class: PlayerClass = CLASS_REG[player_class_key]
        self.player_class.apply_to(self)

    Slot = Literal["weapon", "armor", "artifact"]

    def __str__(self):
        return f"{self.name} ({self.player_class.name})\n" + super().__str__()

    def equip(self, item: object, slot: str) -> None:
        """Equip an item into a slot ("weapon", "armor", "artifact")."""
        current_item = getattr(self, slot, None)
        if current_item:
            # Unequip current item first
            if hasattr(current_item, "on_unequip"):
                current_item.on_unequip(self)
        setattr(self, slot, item)
        if hasattr(item, "on_equip"):
            item.on_equip(self)

    def unequip(self, slot: str) -> None:
        item = getattr(self, slot, None)
        if item:
            if hasattr(item, "on_unequip"):
                item.on_unequip(self)
            setattr(self, slot, None)

    def print_equipment(self) -> None:
        # Console helper (safe no-op for other UIs)
        w = getattr(self.weapon, "name", "Aucune") if self.weapon else "Aucune"
        a = getattr(self.armor, "name", "Aucune") if self.armor else "Aucune"
        r = getattr(self.artifact, "name", "Aucun") if self.artifact else "Aucun"
        print("Équipement actuel :")
        print(f"  Arme     : {w}")
        print(f"  Armure   : {a}")
        print(f"  Artefact : {r}")


