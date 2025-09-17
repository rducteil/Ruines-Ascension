from __future__ import annotations
"""Banque de classes joueur (contenu)."""

from core.player_class import PlayerClass
from core.stats import Stats
from core.attack import Attack
from core.equipment_set import EquipmentSet
from core.equipment import Weapon, Armor, Artifact


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
            crit_multiplier=2.5
            ),
        class_base_equip=EquipmentSet(
            Weapon(name="Glaive rouillé", durability_max=100, bonus_attack=5, description="Un glaive générique rouillé par le sang et le temps"),
            Armor(name="Cuirasse rouillée", durability_max=100, bonus_defense=5, description="Une cuirasse générique rouillée par les coups et l'âge"),
            Artifact(name="Insigne rouillée", durability_max=100, atk_pct=0.05, def_pct=0.05, lck_pct=0.05, description="Une insigne générique rouillée par les larmes et le deuil")
        )
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
        class_base_equip=EquipmentSet(
            Weapon(name="Vieux roseau enchanté", durability_max=100, bonus_attack=5, description="Un simple roseau respectueux des arcanes"),
            Armor(name="Vieux lambeau enchanté", durability_max=100, bonus_defense=5, description="Un simple lambeau docile aux secrets"),
            Artifact(name="Vieux fil de lin enchanté", durability_max=100, atk_pct=0.05, def_pct=0.05, lck_pct=0.05, description="Un simple fil de lin soumis au Mystique")
        )
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
        class_base_equip=EquipmentSet(
            Weapon(name="Lame de ferraille", durability_max=100, bonus_attack=5, description="Une lame de pacotille mais audacieuse face à l'adversité"),
            Armor(name="Gilet de ferraille", durability_max=100, bonus_defense=5, description="Un gilet de pacotille mais tenace face aux difficultés"),
            Artifact(name="Pièce de ferraille", durability_max=100, atk_pct=0.05, def_pct=0.05, lck_pct=0.05, description="Une pièce de pacotille mais fétiche face aux mésaventures")
        )
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
        class_base_equip=EquipmentSet(
            Weapon(name="Pique cabossé", durability_max=100, bonus_attack=5, description="Un pique fragmenté qui vise les jointures"),
            Armor(name="Maille cabossée", durability_max=100, bonus_defense=5, description="Une maille morcelée qui endure les coups"),
            Artifact(name="Bousole cabossée", durability_max=100, atk_pct=0.05, def_pct=0.05, lck_pct=0.05, description="Une bousole accidentée qui guide les égarés")
        )
    ),
    "sentinelle": PlayerClass(
        name="Sentinelle",
        bonus_stats=Stats(defense=40),
        bonus_hp_max=10,
        class_attack=Attack(
            name="Bastion Compresseur", 
            base_damage=20,
            variance=0,
            cost=20
            ),
        class_base_equip=EquipmentSet(
            Weapon(name="Masse émoussée", durability_max=100, bonus_attack=5, description="Une lourde masse imbue de zèle"),
            Armor(name="Plastron émoussée", durability_max=100, bonus_defense=5, description="Un lourd plastron imbu ferveur"),
            Artifact(name="Amulette émoussée", durability_max=100, atk_pct=0.05, def_pct=0.05, lck_pct=0.05, description="Une lourde amulette imbue de piété")
        )
    ),
}