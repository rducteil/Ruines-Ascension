from core.entity import Entity
from core.player_class import CLASSES

class Player(Entity):
    def __init__(self, name, class_name):
        super().__init__(name, **CLASSES[class_name]["stats"])
        self.class_name = class_name
        self.class_attack = CLASSES[class_name]["attack"]
        self.inventory = []
        self.zone = 1
        self.energy = self.base_endurance
        self.weapon = None
        self.armor = None
        self.artifact = None

    def __str__(self):
        return f"{self.name} ({self.class_name})\n" + super().__str__()

    def print_equipment(self):
        print("Équipement actuel :")
        print(f"  Arme     : {self.weapon.name if self.weapon else 'Aucune'}")
        print(f"  Armure   : {self.armor.name if self.armor else 'Aucune'}")
        print(f"  Artefact : {self.artifact.name if self.artifact else 'Aucun'}")
    
    def equip(self, item, slot: str):
        current_item = getattr(self, slot)
        if current_item:
            current_item.on_unequip(self)
        setattr(self, slot, item)
        item.on_equip(self)

    def unequip(self, slot: str):
        current_item = getattr(self, slot)
        if current_item:
            current_item.on_unequip(self)
            setattr(self, slot, None)

    def use_energy(self, amount):
        self.energy -= amount
        if self.energy < 0:
            self.energy = 0

    def restore_energy(self):
        self.energy = self.base_endurance
