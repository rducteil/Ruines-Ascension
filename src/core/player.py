from __future__ import annotations
"""Player : entité jouable.

- Hérite de Entity.
- Pas d'I/O ici.
- Dépend de  core.entity, core.stats, core.player_classes
"""

from typing import TYPE_CHECKING, Literal, TypeAlias

from core.entity import Entity
from core.stats import Stats
from core.player_class import PlayerClass, CLASSES as CLASS_REG

if TYPE_CHECKING:
    from core.equipment import Equipment, Weapon, Armor, Artifact

Slot: TypeAlias = Literal["weapon", "armor", "artifact"]
VALID_SLOT = ("weapon", "armor", "artifact")

class Player(Entity):
    """
        Entité jouable
        init: name, player_class_key, base_stats, base
    """
    def __init__(self, 
                 name: str, 
                 player_class_key: str, 
                 base_stats: Stats, 
                 base_hp_max: int,
                 base_sp_max: int) :
        super().__init__(name=name, base_stats=base_stats, base_hp_max=base_hp_max, base_sp_max=base_sp_max)

        # Equipment slots (optional at start)
        self.weapon: Weapon | None = None
        self.armor: Armor | None = None
        self.artifact: Artifact | None = None

        # Apply class bonuses (stats + resources) if provided
        self.player_class_key = (player_class_key or "").strip().lower()
        self.player_class: PlayerClass = CLASS_REG[player_class_key]
        self.player_class.apply_to(self)


    def __str__(self):
        return f"{self.name} ({self.player_class.name})\n" + super().__str__()

    def equip(self, item: Equipment, slot: Slot) -> None:
        """Equip un item dans slot ("weapon", "armor", "artifact")."""
        # Vérifie le bon slot
        if slot not in VALID_SLOT:
            raise ValueError(f"slot invalide {slot}") 
        # On vérifie que l'item n'a pas de holder
        current_holder: Entity | None = getattr(item, "_holder", None)
        if current_holder and current_holder is not self:
            item.on_unequip(current_holder)
        # On unequip si player a déja un item
        current_item: Equipment | None = getattr(self, slot, None)
        if current_item:
            current_item.on_unequip(self)
        # Donne l'item au player et applique les bonus
        setattr(self, slot, item)
        item.on_equip(self)

    def unequip(self, slot: Slot) -> None:
        # Vérifie le bon slot
        if slot not in VALID_SLOT:
            raise ValueError(f"slot invalide {slot}") 
        item: Equipment | None = getattr(self, slot, None)
        if item:
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


