from __future__ import annotations
"""Offres de ravitaillement (REST/REPAIR/SHOP) + parchemin d’attaque de classe."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Items vendus (ids définis dans content/items.py)
SHOP_ITEMS = [
    {"item_id": "potion_hp_s", "name": "Petite potion de soin", "base_price": 10},
    {"item_id": "potion_sp_s", "name": "Petite potion d’esprit", "base_price": 12},
]

# Parchemin d’attaque de classe (remplace le slot 'skill' du loadout)
CLASS_SCROLL_BASE_PRICE = 50

@dataclass
class ShopOffer:
    kind: str            # "item" | "class_scroll"
    name: str
    price: int
    item_id: str | None = None
    class_key: str | None = None

def price_for_level(base: int, level: int) -> int:
    # petite inflation (≈ +10% / niveau)
    return int(round(base * (1.0 + 0.10 * max(0, level - 1))))

def build_offers(*, zone_level: int, player_class_key: str) -> list[ShopOffer]:
    offers: list[ShopOffer] = []
    class_key = (player_class_key or "").strip().lower()
    for row in SHOP_ITEMS:
        offers.append(ShopOffer(kind="item",
                                name=row["name"],
                                price=price_for_level(row["base_price"], zone_level),
                                item_id=row["item_id"]))
    # Parchemin d’attaque de classe
    offers.append(ShopOffer(kind="class_scroll",
                            name="Parchemin de maîtrise",
                            price=price_for_level(CLASS_SCROLL_BASE_PRICE, zone_level),
                            class_key=class_key))
    return offers

# Paramètres “supply” par défaut
REST_HP_PCT = 30     # % PV
REST_SP_PCT = 30     # % SP
REPAIR_COST_PER_POINT = 2  # 2 or / point de durabilité
