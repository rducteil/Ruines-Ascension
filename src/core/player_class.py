from core.attack import Attack

class PlayerClass:
    def __init__(self, bonus_hp=0, bonus_attack=0, bonus_defense=0, bonus_endurance=0, bonus_luck=0, class_attack=None):
        self.bonus_hp = bonus_hp
        self.bonus_attack = bonus_attack
        self.bonus_defense = bonus_defense
        self.bonus_endurance = bonus_endurance
        self.bonus_luck = bonus_luck
        self.class_attack = class_attack


CLASSES = {
    "guerrier" : PlayerClass(
        bonus_attack = 25,
        bonus_hp = 15,
        bonus_defense = 10,
        class_attack = Attack("Coup de taille", cost=5)
    ),
    "mystique" : PlayerClass(
        bonus_attack = 40,
        bonus_luck = 10,
        class_attack = Attack("Rayon mystique", cost=20)
    ),
    "vagabond" : PlayerClass(
        bonus_endurance = 25,
        bonus_hp = 15,
        bonus_luck = 10,
        class_attack = Attack("Frappe agile", cost=10, crit_multiplier=3)
    ),
    "arpenteur" : PlayerClass(
        bonus_endurance = 25,
        bonus_attack = 15,
        bonus_hp = 10,
        class_attack = Attack("Percé rapide", cost=10)
    ),
    "sentinelle" : PlayerClass(
        bonus_defense = 40,
        bonus_hp = 10,
        class_attack = Attack("Mur écrasant", cost=20)
    )
}
