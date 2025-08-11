from core.stats import Stats
from typing import TypedDict

class PlayerInitKwargs(TypedDict):
    base_stats: Stats
    base_hp_max: int
    base_sp_max: int

def BASE_PLAYER() -> PlayerInitKwargs:
    return {
    "base_stats" : Stats(attack=10, defense=10, luck=5),
    "base_hp_max" : 50,
    "base_sp_max" : 50
    }