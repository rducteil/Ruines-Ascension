import time
from core.player import Player
from ui.console_ui import (
    show_welcome,
    ask_player_name,
    choose_class,
    show_stats
)
from game.game_loop import start_game


def main():
    show_welcome()

    name = ask_player_name()
    class_name = choose_class()

    player = Player(name, class_name)
    show_stats(player, "🔰 Statistiques initiales")

    start_game(player)


if __name__ == "__main__":
    main()
