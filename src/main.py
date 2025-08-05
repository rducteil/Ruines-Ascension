from core.player import Player
from interface.console_ui import game_loop

if __name__ == "__main__":
    player = Player("Elyon", "arpenteur")
    game_loop(player)
