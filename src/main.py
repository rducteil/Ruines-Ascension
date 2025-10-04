from core.stats import Stats
from core.player import Player
from game.game_loop import GameLoop
from ui.console_io import ConsoleIO
from typing import TYPE_CHECKING
import sys, time, threading, os

from core.data_loader import load_player_classes, load_attacks, load_loadouts
from core.loadout import LoadoutManager
from core.data_loader import load_player_classes

if TYPE_CHECKING:
    from core.player import Player
    from core.player_class import PlayerClass
    from game.game_loop import GameIO
CLASSES = load_player_classes()
ATTACKS_REG = load_attacks()
DEFAULT_LOADOUTS = load_loadouts(ATTACKS_REG)
DEFAULT_LOADOUTS = {str(k).strip().lower(): v for (k, v) in DEFAULT_LOADOUTS.items()}

def _choose_class_key(classes_dict: dict) -> str:
    keys = list(classes_dict.keys())  # déjà en minuscules si tu as normalisé
    names = [classes_dict[k].name for k in keys]
    print("Choisis ta classe :")
    for i, nm in enumerate(names, 1):
        print(f"  {i}) {nm}")
    while True:
        ch = input("> ")
        if ch.isdigit() and 1 <= int(ch) <= len(keys):
            return keys[int(ch)-1]

def _resolve_loadout_for(player: Player):
    # candidates: clé interne + nom affiché
    candidates = []
    if player.player_class_key:
        candidates.append(player.player_class_key.strip().lower())
    cls: PlayerClass = player.player_class
    if cls and getattr(cls, "name", None):
        candidates.append(cls.name.strip().lower())

    # essaie dans l'ordre, puis fallback
    for key in candidates:
        lo = DEFAULT_LOADOUTS.get(key)
        if lo is not None:
            return lo
    # fallback: premier loadout dispo
    return next(iter(DEFAULT_LOADOUTS.values()))

def main():
    io = ConsoleIO()
    class_key = _choose_class_key(CLASSES)
    name = input("Choisi ton nom : ")
    p = Player(
        name=name,
        player_class_key=class_key,
        base_stats=Stats(attack=10, defense=10, luck=5),
        base_hp_max=50,
        base_sp_max=20,
    )
    loop = GameLoop(player=p, io=io, seed=42)
    loop.loadouts = LoadoutManager()
    loop.loadouts.set(p, _resolve_loadout_for(p))
    loop.run()

if __name__ == "__main__":
    main()
