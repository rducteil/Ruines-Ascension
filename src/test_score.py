from player import Player
from player_class import CLASSES
from weapon import Weapon
from armor import Armor
from artifact import Artifact

# Crée un joueur de classe Arpenteur
player = Player("Elyon", "arpenteur")

# Affiche ses stats de base
print("Avant équipement :")
print(player)
print()

# Crée des équipements
sword = Weapon("Épée rouillée", durability=10, bonus_attack=15)
shield = Armor("Bouclier usé", durability=20, bonus_defense=10)
charm = Artifact("Porte-bonheur", {"luck": +5, "base_endurance": +10})

# Applique les équipements
sword.on_equip(player)
shield.on_equip(player)
charm.on_equip(player)

# Affiche les stats modifiées
print("Après équipement :")
print(player)
