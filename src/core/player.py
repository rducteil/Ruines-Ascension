from entity import Entity
from player_class import CLASSES

class Player(Entity):
    def __init__(self, name, class_name):
        player_class = CLASSES[class_name]

        super().__init__(
            name=name,
            max_hp=player_class.max_hp,
            base_attack=player_class.base_attack,
            base_defense=player_class.base_defense,
            base_endurance=player_class.base_endurance,
            luck=player_class.luck
        )

        self.class_name = player_class.name
        self.inventory = []
        self.zone = 1
        self.energy = self.base_endurance

        # Équipement initial (facultatif)
        self.weapon = player_class.starting_equipment.get("weapon")
        self.armor = player_class.starting_equipment.get("armor")
        self.artifact = player_class.starting_equipment.get("artifact")

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
