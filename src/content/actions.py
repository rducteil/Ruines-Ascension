from __future__ import annotations
"""Actions et loadouts de départ par classe."""

from core.attack import Attack
from core.effects import PoisonEffect, AttackBuffEffect, DefenseBuffEffect, LuckBuffEffect
from core.loadout import Loadout

# --- actions génériques (setup/payoff) ---

FRAPPER = Attack.basic(name="Frapper", base_damage=6, variance=2, cost=3)
BRISE_GARDE = Attack.heavy(name="Brise-garde", base_damage=12, variance=3, cost=6, ignore_defense_pct=0.25)
CHARGE = Attack(name="Charge", base_damage=0, cost=4, target="self",
                effects=[AttackBuffEffect("Charge", duration=1, potency=4)])

ONDE = Attack.basic(name="Onde mentale", base_damage=5, variance=3, cost=2)
CONCENTRATION = Attack(name="Concentration", base_damage=0, cost=5, target="self",
                      effects=[AttackBuffEffect("Concentration", duration=1, potency=5)])
SIPHON = Attack(name="Siphon vital", base_damage=3, variance=1, cost=4, true_damage=4)

COUP_RAPIDE = Attack.basic(name="Coup rapide", base_damage=5, variance=3, cost=2)
LAME_TOXIQUE = Attack(name="Lame toxique", base_damage=4, variance=1, cost=3,
                      effects=[PoisonEffect("Poison", duration=2, potency=3)])
PARI = Attack(name="Pari", base_damage=0, cost=4, target="self",
              effects=[LuckBuffEffect("Pari: chance↑", duration=2, potency=5),
                       DefenseBuffEffect("Pari: défense↓", duration=2, potency=-3)])

PERCEE = Attack.basic(name="Percée", base_damage=6, variance=2, cost=3)
MARQUE = Attack(name="Marque", base_damage=0, cost=3, target="enemy",
                effects=[DefenseBuffEffect("Armure fragilisée", duration=2, potency=-4)])
FENTE = Attack(name="Fente oblique", base_damage=8, variance=1, cost=5)

HEURT = Attack.basic(name="Heurt de bouclier", base_damage=5, variance=1, cost=2)
GARDE = Attack(name="Garde", base_damage=0, cost=4, target="self",
               effects=[DefenseBuffEffect("Garde", duration=1, potency=6)])
ECRASEMENT = Attack.heavy(name="Écrasement", base_damage=11, variance=1, cost=6)

# --- loadouts de départ (3 slots) ---
DEFAULT_LOADOUT_BY_CLASS = {
    "guerrier":  Loadout(primary=FRAPPER,  skill=BRISE_GARDE, utility=CHARGE),
    "mystique":  Loadout(primary=ONDE,     skill=SIPHON,      utility=CONCENTRATION),
    "vagabond":  Loadout(primary=COUP_RAPIDE, skill=LAME_TOXIQUE, utility=COUP_RAPIDE),  # remplace "Pari" si tu crées LuckBuffEffect
    "arpenteur": Loadout(primary=PERCEE,   skill=FENTE,       utility=MARQUE),
    "sentinelle":Loadout(primary=HEURT,    skill=ECRASEMENT,  utility=GARDE),
}

def default_loadout_for_class(class_key: str) -> Loadout:
    # copie défensive (reconstruit des Attack via __dict__)
    base = DEFAULT_LOADOUT_BY_CLASS.get(class_key, DEFAULT_LOADOUT_BY_CLASS["guerrier"])
    return Loadout(
        primary=Attack(**base.primary.__dict__),
        skill=Attack(**base.skill.__dict__),
        utility=Attack(**base.utility.__dict__),
    )

def with_class_attack(loadout: Loadout, class_attack: Attack) -> Loadout:
    """Remplace l’emplacement 'skill' par l’attaque de classe achetée."""
    return Loadout(
        primary=Attack(**loadout.primary.__dict__),
        skill=Attack(**class_attack.__dict__),     # upgrade slot
        utility=Attack(**loadout.utility.__dict__),
    )
