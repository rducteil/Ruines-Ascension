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
DEFAULT_LOADOUTS = {str(k).strip().lower(): v for (k, v) in DEFAULT_LOADOUTS.items()}

def _choose_class_key(io, classes_dict):
    keys = list(classes_dict.keys())  # déjà en minuscules si tu as normalisé
    names = [classes_dict[k].name for k in keys]
    print("Choisis ta classe :")
    for i, nm in enumerate(names, 1):
        print(f"  {i}) {nm}")
    while True:
        ch = input("> ")
        if ch.isdigit() and 1 <= int(ch) <= len(keys):
            return keys[int(ch)-1]

def _resolve_loadout_for(player):
    # candidates: clé interne + nom affiché
    candidates = []
    if getattr(player, "player_class_key", None):
        candidates.append(player.player_class_key.strip().lower())
    cls = getattr(player, "player_class", None)
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
    class_key = _choose_class_key(io, CORE_CLASSES)
    p = Player(
        name="Moi",
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
