from core.player_class import CLASSES

def show_welcome():
    print("=== Bienvenue dans Ruines Ascension ===\n")

def ask_player_name():
    return input("🧝‍♂️ Entrez votre nom d'aventurier : ").strip()

def choose_class():
    print("\n📜 Choisissez une classe :")
    for i, class_name in enumerate(CLASSES.keys(), 1):
        print(f"{i}. {class_name.capitalize()}")

    while True:
        choice = input("Votre choix > ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CLASSES):
            class_name = list(CLASSES.keys())[int(choice) - 1]
            return class_name
        print("❌ Choix invalide.")

def ask_play_again():
    response = input("\n🔁 Rejouer un combat ? (o/n) > ").lower()
    return response == "o"

def show_stats(player, label="Stats du joueur :"):
    print(f"\n📊 {label}")
    print(player)
    player.print_equipment()
