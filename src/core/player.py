from core.entity import Entity
from core.player_class import CLASSES

base_stats = {
    "max_hp" : 50, 
    "base_attack" : 10,
    "base_defense" : 10,
    "base_endurance" : 50,
    "luck" : 5
}

class Player(Entity):
    def __init__(self, name, type):
        super().__init__(name, **base_stats)
        self.type = type
        self.max_hp += CLASSES[type].bonus_hp
        self.base_attack += CLASSES[type].bonus_attack
        self.base_defense += CLASSES[type].bonus_defense
        self.base_endurance += CLASSES[type].bonus_endurance
        self.energy = self.base_endurance
        self.luck += CLASSES[type].bonus_luck
        self.class_attack = CLASSES[type].class_attack

    def __str__(self):
        return f"{self.name} ({self.type})\n" + super().__str__()

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

    def restore_energy(self, amount):
        self.energy += amount
        if self.energy >= self.base_endurance:
            self.energy = self.base_endurance
