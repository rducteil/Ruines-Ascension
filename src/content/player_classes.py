from __future__ import annotations
"""Banque de classes joueur (contenu)."""

from core.player_class import PlayerClass
from core.stats import Stats
from core.attack import Attack

CLASSES: dict[str, PlayerClass] = {
    "guerrier": PlayerClass(
        name="Guerrier",
        bonus_stats=Stats(attack=25, defense=10),
        bonus_hp_max=15,
        class_attack=Attack(
            name="Fracas Intégral",
            base_damage=15,
            variance=2,
            cost=10,
            crit_multiplier=2.5),
    ),
    "mystique": PlayerClass(
        name="Mystique",
        bonus_stats=Stats(attack=40, luck=10),
        bonus_sp_max=20,
        class_attack=Attack(
            name="Rayon mystique", 
            base_damage=10,
            variance=6,
            cost=18,
            true_damage=5
        ),
    ),
    "vagabond": PlayerClass(
        name="Vagabond",
        bonus_stats=Stats(luck=20),
        bonus_hp_max=10,
        bonus_sp_max=20,
        class_attack=Attack(
            name="Apogée Fatale", 
            base_damage=10,
            variance=5,
            cost=12, 
            crit_multiplier=3
        ),
    ),
    "arpenteur": PlayerClass(
        name="Arpenteur",
        bonus_stats=Stats(attack=15),
        bonus_hp_max=10,
        bonus_sp_max=25,
        class_attack=Attack(
            name="Point de Rupture", 
            base_damage=9,
            variance=2,
            cost=10,
            ignore_defense_pct=0.50
        ),
    ),
    "sentinelle": PlayerClass(
        name="Sentinelle",
        bonus_stats=Stats(defense=40),
        bonus_hp_max=10,
        class_attack=Attack(
            name="Bastion compresseur", 
            base_damage=20,
            variance=0,
            cost=20
        ),
    ),
}