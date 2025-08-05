from equipment import Equipment

class Artifact(Equipment):
    def __init__(self, name, effect_dict, description=""):
        # Artefacts ont souvent une durabilité "infinie"
        super().__init__(name, durability=999, description=description)
        self.effect = effect_dict  # exemple : {"luck": +10, "base_endurance": +5}

    def on_equip(self, entity):
        for stat, value in self.effect.items():
            if hasattr(entity, stat):
                setattr(entity, stat, getattr(entity, stat) + value)

    def on_unequip(self, entity):
        for stat, value in self.effect.items():
            if hasattr(entity, stat):
                setattr(entity, stat, getattr(entity, stat) - value)
