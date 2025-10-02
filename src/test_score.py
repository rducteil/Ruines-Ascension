from core.player import Player
from core.data_loader import load_player_classes, load_equipment_banks
from core.equipment import Equipment
from core.stats import Stats

CLASSES = load_player_classes()
player = Player("Elyon", "arpenteur", base_stats=Stats(8, 4, 2, 2.0), base_hp_max=35, base_sp_max=15)

# Affiche ses stats de base
print("Avant équipement :")
print(player)
player.print_equipment()
print()

# Crée des équipements
weapon_bank, armor_bank, artifact_bank = load_equipment_banks()
sword = next(iter(weapon_bank.values())).clone()
shield = next(iter(armor_bank.values())).clone()
charm = next(iter(artifact_bank.values())).clone()

# Applique les équipements
player.equip(sword, "weapon")
player.equip(shield, "armor")
player.equip(charm, "artifact")

# Affiche les stats modifiées
print("Après équipement :")
print(player)
player.print_equipment()

# Remplacement d'arme
new_sword = next(iter(weapon_bank.values())).clone()
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