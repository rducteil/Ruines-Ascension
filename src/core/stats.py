from dataclasses import dataclass

@dataclass
class Stats:
    attack: int
    defense: int
    luck: int
    crit_multiplier: float = 2.0


