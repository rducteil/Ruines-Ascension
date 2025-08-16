from core.stats import Stats
from core.player import Player
from game.game_loop import GameLoop
from ui.console_io import ConsoleIO

# registre core + fusion "content" puis "data"
from core.player_class import PlayerClass, CLASSES as CORE_CLASSES 
from content.player_classes import CLASSES as CONTENT_CLASSES
CORE_CLASSES.update(CONTENT_CLASSES)

from core.data_loader import load_player_classes, load_attacks, load_loadouts
from core.loadout_manager import LoadoutManager
from core.data_loader import load_player_classes
CORE_CLASSES.update(load_player_classes())

ATTACKS_REG = load_attacks()
DEFAULT_LOADOUTS = load_attacks()

def main():
    # Crée un joueur (exemple)
    p = Player(
        name="Moi",
        player_class_key="Guerrier",
        base_stats=Stats(attack=10, defense=10, luck=5),
        base_hp_max=50,
        base_sp_max=20,
    )

    io = ConsoleIO()
    loop = GameLoop(player=p, io=io, seed=42)
    loop.loadouts = LoadoutManager
    loop.loadouts.set(p, DEFAULT_LOADOUTS[p.player_class_key.lower()])
    loop.run()

if __name__ == "__main__":
    main()
