class Equipment:
    def __init__(self, name, durability, description=""):
        self.name = name
        self.max_durability = durability
        self.current_durability = durability
        self.description = description

    def is_broken(self):
        return self.current_durability <= 0

    def reduce_durability(self, amount=1):
        self.current_durability -= amount
        if self.current_durability < 0:
            self.current_durability = 0

    def restore_durability(self):
        self.current_durability = self.max_durability

    def on_equip(self, entity):
        """
        Méthode à surcharger dans Weapon/Armor/Artifact.
        Définir ce que fait l’objet une fois équipé.
        """
        pass

    def get_info(self):
        return f"{self.name} (Durabilité: {self.current_durability}/{self.max_durability})"
