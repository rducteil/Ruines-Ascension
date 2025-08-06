from core.player import Player
from core.enemy import Enemy
from core.player_class import CLASSES
from core.combat import simulate_combat

def choose_class():
    print("=== Sélection de classe ===")
    for i, class_name in enumerate(CLASSES.keys(), 1):
        print(f"{i}. {class_name.capitalize()}")
    
    while True:
        choice = input("Choisis ton numéro de classe > ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CLASSES):
            class_name = list(CLASSES.keys())[int(choice) - 1]
            return class_name
        print("❌ Choix invalide.")

def main():
    print("=== Bienvenue dans Ruines Ascension ===")
    player_name = input("Entre ton nom d'aventurier : ")
    class_name = choose_class()

    player = Player(player_name, class_name)
    print(f"\n✅ {player.name}, {class_name.capitalize()} prêt pour l'ascension !\n")

    # Boucle de test : un combat à la fois
    while True:
        print("\nUne nouvelle créature t'attend...")
        enemy = Enemy("Bête sauvage", max_hp=100, base_attack=30, base_defense=20, base_endurance=50, luck=10)

        simulate_combat(player, enemy)

        if not player.is_alive():
            print("\n💀 Game Over.")
            break

        again = input("\nSouhaites-tu combattre un nouvel ennemi ? (o/n) > ").strip().lower()
        if again != "o":
            print("\n🏁 Fin de la session. À bientôt !")
            break

if __name__ == "__main__":
    main()
