import random
from core.effects import Effect

class Attack:
    def __init__(self, name, base_damage=0, cost=0, crit_multiplier=2, effect_list: list[Effect] = [None]):
        self.name = name
        self.base_damage = base_damage
        self.effect_list = effect_list
        self.cost = cost
        self.crit_multiplier = crit_multiplier

    
""" def calculate_damage(attacker, defender, crit_multiplier=2):
    base = attacker.base_attack
    weapon_bonus = attacker.weapon.bonus_attack if attacker.weapon else 0
    total_attack = base + weapon_bonus

    defense = defender.base_defense
    armor_bonus = defender.armor.bonus_defense if defender.armor else 0
    total_defense = defense + armor_bonus

    is_crit = random.random() < (attacker.luck / 200)  # ex : 20% si luck = 40
    damage = max(total_attack - total_defense, 0)

    if is_crit:
        damage *= crit_multiplier

    return int(damage), is_crit """
