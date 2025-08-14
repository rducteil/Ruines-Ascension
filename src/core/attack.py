from __future__ import annotations
"""Description déclarative (dégâts de base, variance, coût, effets) sans I/O ni RNG."""

from dataclasses import dataclass, field
from typing import Literal, Optional
from core.effects import Effect 

@dataclass
class Attack:
    """Données d'une attaque ; le calcul/hasard est fait par CombatEngine.

    Champs:
      - base_damage: dégâts de base
      - variance: delta tiré par le moteur dans [-variance, +variance]
      - cost: coût en SP
      - crit_multiplier: multiplicateur en cas de critique (défaut x2)
      - ignore_defense_pct: proportion de DEF ignorée (0..1)
      - true_damage: dégâts bruts additionnels (ajoutés après calcul)
      - effects: effets appliqués SI l'attaque touche (ex.: PoisonEffect)
    """
    name: str
    base_damage: int = 0
    variance: int = 0               # delta tiré dans [-variance, +variance]
    cost: int = 0                   # coût en SP
    crit_multiplier: float = 2.0    # x2 par défaut (peut varier en fonction de l'attaque)
    effects: list [Effect] = field(default_factory=list)

    # Modifs de calcul (optionnelles)
    ignore_defense_pct: float = 0.0   # ex: 0.25 => ignore 25% de DEF
    true_damage: int = 0              # dégâts bruts ajoutés après calcul

    target: Literal["enemy", "self"] = "enemy"

    def __post_init__(self):
        # validation / clamps
        self.base_damage = max(0, int(self.base_damage))
        self.variance = max(0, int(self.variance))
        self.cost = max(0, int(self.cost))
        self.crit_multiplier = max(1.0, float(self.crit_multiplier))
        self.ignore_defense_pct = float(self.ignore_defense_pct)
        if self.ignore_defense_pct < 0.0: self.ignore_defense_pct = 0.0
        if self.ignore_defense_pct > 1.0: self.ignore_defense_pct = 1.0
        self.true_damage = max(0, int(self.true_damage))
        # copie défensive de la liste (au cas où on passe une liste partagée)
        self.effects = list(self.effects)

    # Fabriques pratiques
    @staticmethod
    def basic(name: str = "Attaque", base_damage: int = 5, variance: int = 2, cost: int = 0) -> "Attack":
        return Attack(name=name, base_damage=base_damage, variance=variance)
    
    @staticmethod
    def heavy(name: str = "Attaque lourde", *, base_damage: int = 10, variance: int = 3,
              cost: int = 6, ignore_defense_pct: float = 0.25) -> "Attack":
        return Attack(name=name, base_damage=base_damage, variance=variance, cost=cost,
                      ignore_defense_pct=ignore_defense_pct)

    @staticmethod
    def skill(name: str = "Technique", *, base_damage: int = 4, variance: int = 1,
              cost: int = 5, true_damage: int = 6) -> "Attack":
        return Attack(name=name, base_damage=base_damage, variance=variance, cost=cost,
                      true_damage=true_damage)
