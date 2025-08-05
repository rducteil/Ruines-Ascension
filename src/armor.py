from equipment import Equipment

class Armor(Equipment):
    def __init__(self, name, durability, bonus_defense, description=""):
        super().__init__(name, durability, description)
        self.bonus_defense = bonus_defense

    def on_equip(self, entity):
        entity.base_defense += self.bonus_defense

    def on_unequip(self, entity):
        entity.base_defense -= self.bonus_defense
