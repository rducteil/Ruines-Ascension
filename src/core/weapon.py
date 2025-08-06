from core.equipment import Equipment

class Weapon(Equipment):
    def __init__(self, name, durability, bonus_attack, special_attack=None, description=""):
        super().__init__(name, durability, description)
        self.bonus_attack = bonus_attack  # Valeur d'attaque supplémentaire
        self.special_attack = special_attack    # Instance d'Attack

    def on_equip(self, entity):
        # Applique le bonus d’attaque à l’entité (joueur ou ennemi)
        entity.base_attack += self.bonus_attack

    def on_unequip(self, entity):
        # Retire le bonus quand l’arme est déséquipée (optionnel)
        entity.base_attack -= self.bonus_attack
