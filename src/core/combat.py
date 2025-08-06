import random, time
from core.attack import calculate_damage

def simulate_combat(player, enemy):
    print(f"\n⚔️  Combat : {player.name} vs {enemy.name} !\n")

    turn = 1
    while player.is_alive() and enemy.is_alive():
        print(f"🕒 Tour {turn}")
        print(f"{player.name} : {player.current_hp}/{player.max_hp} PV | END : {player.base_endurance}")
        print(f"{enemy.name} : {enemy.current_hp}/{enemy.max_hp} PV\n")

        # Tour du joueur
        print("👉 Que veux-tu faire ?")
        time.sleep(0.2)
        print("1. Attaque de base (coût : -5 END)")
        time.sleep(0.5)
        print(f"2. Attaque de classe (coût : -{player.class_attack.cost} END)")
        time.sleep(0.5)
        if player.weapon and player.weapon.special_attack:
            print(f"3. Attaque spéciale (arme, coût : -{player.weapon.special.attack.cost} END)")
            time.sleep(0.5)
        print("4. Passer (récupérer endurance)")
        time.sleep(0.5)

        choice = input("Action > ").strip()

        if choice == "1":
            damage, crit = calculate_damage(player, enemy)
            player.base_endurance -= 5
            enemy.take_damage(damage)
            print(f"Tu attaques normalement {enemy.name} et infliges {damage} dégâts !")
            time.sleep(0.5)
        
        elif choice == "2":
            attack = player.class_attack
            if player.base_endurance >= attack.cost:
                damage, crit = attack.calculate(player, enemy)
                player.base_endurance -= attack.cost
                enemy.take_damage(damage)
                print(f"Tu utilises {attack.name} et infliges {damage} dégâts.")
                if crit:
                    print("💥 Coup critique !")
                time.sleep(0.5)
            else:
                print("❌ Pas assez d’endurance !")
                time.sleep(0.5)

        elif choice == "3" and player.weapon and player.weapon.special_attack:
            attack = player.weapon.special_attack
            if player.base_endurance >= attack.cost:
                damage, crit = attack.calculate(player, enemy)
                player.base_endurance -= attack.cost
                enemy.take_damage(damage)
                print(f"Tu utilises {attack.name} et infliges {damage} dégâts.")
                if crit:
                    print("💥 Coup critique !")
            else:
                print("❌ Pas assez d’endurance !")
            time.sleep(0.5)

        elif choice == "4":
            player.base_endurance += 10
            print("Tu prends un moment pour récupérer ton souffle...")
            time.sleep(0.5)

        else:
            print("❌ Action invalide. Tu perds ton tour.")
            time.sleep(0.5)

        if not enemy.is_alive():
            print(f"✅ {enemy.name} est vaincu !")
            time.sleep(0.5)
            break

        # Tour de l’ennemi
        print(f"\n{enemy.name} prépare une attaque...")
        time.sleep(0.2)
        damage, crit = calculate_damage(enemy, player)
        player.take_damage(damage)
        print(f"{enemy.name} t’attaque et inflige {damage} dégâts !")
        if crit:
            print("💥 Coup critique ennemi !")
        time.sleep(0.5)

        turn += 1

        if not player.is_alive():
            print(f"\n☠️ Tu as été vaincu par {enemy.name}...\n")
            time.sleep(0.5)
            break
