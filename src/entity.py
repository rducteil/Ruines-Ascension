class Entity:
    def __init__(self, name, max_hp, base_attack, base_defense, base_endurance, luck):
        self.name = name
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.base_attack = base_attack
        self.base_defense = base_defense
        self.base_endurance = base_endurance
        self.luck = luck

        self.weapon = None
        self.armor = None
        self.artifact = None

    def is_alive(self):
        return self.current_hp > 0

    def take_damage(self, amount):
        self.current_hp -= amount
        if self.current_hp < 0:
            self.current_hp = 0

    def heal(self, amount):
        self.current_hp += amount
        if self.current_hp > self.max_hp:
            self.current_hp = self.max_hp
