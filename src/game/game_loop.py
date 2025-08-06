import random
from core.enemy import Enemy
from core.player import Player
from core.combat import simulate_combat
from ui.console_ui import show_stats, ask_play_again

SECTION_TYPES = ["combat", "ravitaillement", "evenement"]


def generate_enemy(zone_level):
    return Enemy(
        name=f"Créature de la zone {zone_level}",
        max_hp=80 + zone_level * 20,
        base_attack=20 + zone_level * 5,
        base_defense=15 + zone_level * 5,
        base_endurance=40 + zone_level * 10,
        luck=10 + zone_level * 2,
    )


def generate_boss(zone_level):
    return Enemy(
        name=f"BOSS de la zone {zone_level}",
        max_hp=200 + zone_level * 50,
        base_attack=40 + zone_level * 10,
        base_defense=30 + zone_level * 10,
        base_endurance=60 + zone_level * 15,
        luck=20 + zone_level * 5,
    )


def ravitaillement(player):
    print("\n☕️ Ravitaillement : Tu reprends des forces.")
    player.heal(30)
    player.base_endurance += 20
    print("+30 PV, +20 END")
    show_stats(player)


def evenement(player):
    print("\n🕷️ Événement : Une rencontre imprévue...")
    effet = random.choice(["bonus", "malus", "piege"])

    if effet == "bonus":
        print("Tu trouves un ancien totem : +10 CHANCE")
        player.luck += 10
    elif effet == "malus":
        print("Une brume obscure te fatigue : -15 END")
        player.base_endurance = max(0, player.base_endurance - 15)
    elif effet == "piege":
        print("Un piège ! Tu perds 20 PV.")
        player.take_damage(20)

    show_stats(player)


def play_zone(player, zone_level=1):
    print(f"\n▶️ Début de la zone {zone_level} !")
    section_count = 3 + zone_level  # +1 par zone

    for section in range(1, section_count + 1):
        print(f"\n--- Section {section}/{section_count} ---")
        section_type = random.choice(SECTION_TYPES)

        if section_type == "combat":
            enemy = generate_enemy(zone_level)
            simulate_combat(player, enemy)
            if not player.is_alive():
                return False  # game over

        elif section_type == "ravitaillement":
            ravitaillement(player)

        elif section_type == "evenement":
            evenement(player)

    # Boss final de la zone
    print("\n👹 Combat de boss imminent !")
    boss = generate_boss(zone_level)
    simulate_combat(player, boss)

    if not player.is_alive():
        return False

    print(f"\n🌟 Zone {zone_level} terminée avec succès !")
    return True


def start_game(player):
    zone = 1
    while True:
        survived = play_zone(player, zone_level=zone)
        if not survived:
            print("\n☠️ Tu as échoué dans la tour...")
            break

        if not ask_play_again():
            print("\n🏋️ Fin de l'exploration. Tu t'arrêtes au niveau de la zone", zone)
            break

        zone += 1
