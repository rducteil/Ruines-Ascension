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
        return (
            f"{self.name} ({self.class_name})\n"
            f"PV     : {self.current_hp}/{self.max_hp}\n"
            f"ATQ    : {self.base_attack}\n"
            f"DEF    : {self.base_defense}\n"
            f"END    : {self.base_endurance}\n"
            f"CHANCE : {self.luck}"
        )


    def use_energy(self, amount):
        self.energy -= amount
        if self.energy < 0:
            self.energy = 0

    def restore_energy(self):
        self.energy = self.base_endurance
