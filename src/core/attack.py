import random

class Attack:
    def __init__(self, name, power, cost=0, crit_multiplier=2):
        self.name = name
        self.power = power
        self.cost = cost
        self.crit_multiplier = crit_multiplier

    def calculate(self, attacker, defender):
        return calculate_damage(attacker, defender, self.power, self.crit_multiplier)
    
def calculate_damage(attacker, defender, power=1.0, crit_multiplier=2):
    base = attacker.base_attack
    weapon_bonus = attacker.weapon.bonus_attack if attacker.weapon else 0
    total_attack = (base + weapon_bonus) * power

    defense = defender.base_defense
    armor_bonus = defender.armor.bonus_defense if defender.armor else 0
    total_defense = defense + armor_bonus

    is_crit = random.random() < (attacker.luck / 200)  # ex : 20% si luck = 40
    damage = max(total_attack - total_defense, 0)

    if is_crit:
        damage *= crit_multiplier

    print(f"[DEBUG] Base ATQ : {attacker.base_attack}")
    print(f"[DEBUG] Bonus arme : {attacker.weapon.bonus_attack if attacker.weapon else 0}")

    return int(damage), is_crit

