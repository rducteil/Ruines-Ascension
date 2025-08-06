from core.entity import Entity

class Enemy(Entity):
    def __init__(self, name, max_hp, base_attack, base_defense, base_endurance, luck, behavior=None):
        super().__init__(name, max_hp, base_attack, base_defense, base_endurance, luck)
        self.behavior = behavior  # "agressif", "défensif", etc.
        self.effect = None        # effet spécial du monstre

    def choose_action(self):
        # Placeholder, tu pourras personnaliser plus tard
        return "basic_attack"
    
    
