from dataclasses import dataclass

@dataclass
class Stats:
    attack: int = 0
    defense: int = 0
    luck: int = 0
    crit_multiplier: float = 2.0


