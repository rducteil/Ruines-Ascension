# main.py
from core.stats import Stats
from core.player import Player
from game.game_loop import GameLoop
from ui.console_io import ConsoleIO

def main():
    # Crée un joueur (exemple)
    p = Player(
        name="Moi",
        player_class_key="guerrier",
        base_stats=Stats(attack=10, defense=10, luck=5),
        base_hp_max=50,
        base_sp_max=20,
    )

    io = ConsoleIO()
    loop = GameLoop(player=p, io=io, seed=42)
    loop.run()

if __name__ == "__main__":
    main()
