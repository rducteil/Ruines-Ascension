from core.player import Player
from core.player_class import CLASSES
from core.weapon import Weapon
from core.armor import Armor
from core.artifact import Artifact
from core.enemy import Enemy
from core.combat import *


def game_loop(player):
    print("🌀 Bienvenue dans Ruines : Ascension !")
    print(f"Explorateur : {player.name} ({player.class_name})")
    
    while player.is_alive():
        print("\n📍 Nouvelle action :")
        print("1. Combattre")
        print("2. Explorer")
        print("3. Se ravitailler")
        print("4. Voir équipement")
        print("5. Quitter")

        choice = input("Choix > ")

        if choice == "1":
            # Création simple d'un ennemi
            enemy = Enemy("Créature étrange", max_hp=60, base_attack=20, base_defense=10, base_endurance=50, luck=5)
            print(f"\n⚔️ Tu affrontes {enemy.name} !")
            simulate_combat(player, enemy)

        elif choice == "2":
            print("🔍 Tu explores un couloir en ruine... Rien pour le moment.")

        elif choice == "3":
            print("🍞 Tu te ravitailles. (WIP : régénération à implémenter)")

        elif choice == "4":
            print("\n📊 Stats du joueur :")
            print(player)
            player.print_equipment()

        elif choice == "5":
            print("👋 Fin de l’exploration.")
            break

        else:
            print("❌ Choix invalide.")

    if not player.is_alive():
        print("☠️ Tu es mort dans la tour. Fin de la partie.")
