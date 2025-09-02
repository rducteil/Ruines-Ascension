from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True, kw_only=True)
class Stats:
    """
        Stats fixe (attaque, défense, chance, multiplicateur crit)
        args: attack, defense, luck, crit_multplier
    """
    attack: int = 0
    defense: int = 0
    luck: int = 0
    crit_multiplier: float = 2.0

    def __add__(self, other: Stats) -> Stats:
        return Stats(
            self.attack + other.attack,
            self.defense + other.defense,
            self.luck + other.luck,
            max(self.crit_multiplier, other.crit_multiplier),
        )

    def __sub__(self, other: Stats) -> Stats:
        return Stats(
            self.attack - other.attack,
            self.defense - other.defense,
            self.luck - other.luck,
            self.crit_multiplier,  # on ne “soustrait” pas un crit mult
        )

    def scaled(self, pct: float) -> Stats:
        return Stats(
            int(round(self.attack * pct)),
            int(round(self.defense * pct)),
            int(round(self.luck * pct)),
            self.crit_multiplier,
        )


