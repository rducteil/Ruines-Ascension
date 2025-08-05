class PlayerClass:
    def __init__(self, name, max_hp, base_attack, base_defense, base_endurance, luck, starting_equipment=None):
        self.name = name
        self.max_hp = max_hp
        self.base_attack = base_attack
        self.base_defense = base_defense
        self.base_endurance = base_endurance
        self.luck = luck
        self.starting_equipment = starting_equipment or {}

# Dictionnaire des classes jouables
CLASSES = {
    "vagabond": PlayerClass(
        name="Vagabond",
        max_hp=100,
        base_attack=70,
        base_defense=60,
        base_endurance=150,
        luck=120
    ),
    "mystique": PlayerClass(
        name="Mystique",
        max_hp=80,
        base_attack=250,
        base_defense=50,
        base_endurance=70,
        luck=50
    ),
    "gardien": PlayerClass(
        name="Gardien",
        max_hp=200,
        base_attack=50,
        base_defense=150,
        base_endurance=50,
        luck=50
    ),
    "tacticien": PlayerClass(
        name="Tacticien",
        max_hp=100,
        base_attack=100,
        base_defense=100,
        base_endurance=100,
        luck=100
    ),
    "arpenteur": PlayerClass(
        name="Arpenteur",
        max_hp=120,
        base_attack=80,
        base_defense=80,
        base_endurance=150,
        luck=70
    ),
}
