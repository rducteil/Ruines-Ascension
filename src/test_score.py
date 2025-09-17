from core.player import Player
from content.player_classes import CLASSES
from core.equipment import Weapon, Armor, Artifact

# Crée un joueur de classe Arpenteur
player = Player("Elyon", "arpenteur")

# Affiche ses stats de base
print("Avant équipement :")
print(player)
player.print_equipment()
print()

# Crée des équipements
sword = Weapon("Épée rouillée", durability=10, bonus_attack=15)
shield = Armor("Bouclier usé", durability=20, bonus_defense=10)
charm = Artifact("Porte-bonheur", {"luck": +5, "base_endurance": +10})

# Applique les équipements
player.equip(sword, "weapon")
player.equip(shield, "armor")
player.equip(charm, "artifact")

# Affiche les stats modifiées
print("Après équipement :")
print(player)
player.print_equipment()

# Remplacement d'arme
new_sword = Weapon("Sabre d’acier", durability=25, bonus_attack=25)
player.equip(new_sword, "weapon")

# Affiche les stats apres changement d'arme
print("Après changement :")
print(player)
player.print_equipment()

# On retire la protection
player.unequip("armor")

# Afficher les stats apres enlever protection
print("Apres enlever protection :")
print(player)
player.print_equipment()