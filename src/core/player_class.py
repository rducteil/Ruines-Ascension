from core.attack import Attack

CLASSES = {
    "guerrier": {
        "stats": {
            "max_hp": 200,
            "base_attack": 100,
            "base_defense": 100,
            "base_endurance": 50,
            "luck": 50
        },
        "attack": Attack("Coup de taille", power=1.0, cost=10)
    },

    "mystique": {
        "stats": {
            "max_hp": 50,
            "base_attack": 300,
            "base_defense": 50,
            "base_endurance": 50,
            "luck": 50
        },
        "attack": Attack("Rayon mystique", power=1.5, cost=20)
    },

    "vagabond": {
        "stats": {
            "max_hp": 100,
            "base_attack": 50,
            "base_defense": 50,
            "base_endurance": 200,
            "luck": 100
        },
        "attack": Attack("Frappe agile", power=0.8, cost=5, crit_multiplier=3)
    },

    "arpenteur": {
        "stats": {
            "max_hp": 120,
            "base_attack": 80,
            "base_defense": 80,
            "base_endurance": 150,
            "luck": 70
        },
        "attack": Attack("Percée rapide", power=1.1, cost=10)
    },

    "sentinelle": {
        "stats": {
            "max_hp": 150,
            "base_attack": 50,
            "base_defense": 200,
            "base_endurance": 50,
            "luck": 50
        },
        "attack": Attack("Mur écrasant", power=1.2, cost=15)
    }
}
