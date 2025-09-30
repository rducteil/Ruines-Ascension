from __future__ import annotations
"""Player : entité jouable.

- Hérite de Entity.
- Pas d'I/O ici.
- Dépend de  core.entity, core.stats, core.player_classes
"""

from typing import TYPE_CHECKING, Literal, TypeAlias

from core.entity import Entity
from core.player_class import PlayerClass
from content.player_classes import CLASSES as CLASSES_CONTENT
from core.equipment_set import EquipmentSet, NO_EQUIP

if TYPE_CHECKING:
    from core.equipment import Equipment, Weapon, Armor, Artifact
    from core.stats import Stats

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

        # Equipment slots:
        self.equipment: EquipmentSet = EquipmentSet(weapon=NO_EQUIP.weapon, armor=NO_EQUIP.armor, artifact=NO_EQUIP.artifact)

        # Applique bonus de classe (stats + resources + equip) if provided
        self.player_class_key = (player_class_key or "").strip().lower()
        self.player_class: PlayerClass = CLASSES_CONTENT[player_class_key]
        self.player_class.apply_to(self)
        self.class_attack_unlocked: bool = False


    def __str__(self):
        return f"{self.name} ({self.player_class.name})\n" + super().__str__()

    def equip(self, new_item: "Equipment"):
        """Equipe un item dans le bon slot du set"""
        # Vérifie que c'est le bon slot
        slot = new_item._slot
        if slot not in VALID_SLOT:
            raise ValueError(f"slot invalid {slot}")
        # Vérifie que l'item n'a pas de holder
        current_holder: "Player" | None = getattr(new_item, "_holder", None)
        if current_holder and current_holder is not self:
            new_item.on_unequip(current_holder)
        # On unequip l'item présent, equip le nouvel item et actualise le set
        current_item: "Equipment" = getattr(self.equipment, slot, None)
        current_item.on_unequip(self)
        new_item.on_equip(self)
        self.equipment.replace(slot=slot, item=new_item)

    def unequip(self, slot: Slot) -> None:
        # Vérifie le bon slot
        if slot not in VALID_SLOT:
            raise ValueError(f"slot invalide {slot}") 
        item: "Equipment" = self.equipment.get(slot)
        item.on_unequip(self)
        no_equip : "Equipment" = getattr(NO_EQUIP, slot, None)
        no_equip.on_equip(self)
        self.equipment.replace(slot=slot, item=no_equip)
            

    def print_equipment(self) -> None:
        # Console helper (safe no-op for other UIs)
        w = self.equipment.weapon
        a = self.equipment.armor
        r = self.equipment.artifact
        print("Équipement actuel :")
        print(f"  Arme     : {w.name} ({w.description})")
        print(f"  Armure   : {a.name} ({a.description})")
        print(f"  Artefact : {r.name} ({r.description})")


