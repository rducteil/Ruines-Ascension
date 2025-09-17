from __future__ import annotations
"""Quelques items concrets pour tester l'inventaire."""

from typing import Optional, TYPE_CHECKING
from core.item import Consumable
from core.combat import CombatEvent

if TYPE_CHECKING:
    from core.entity import Entity
    from core.combat import CombatContext


class SmallHealingPotion(Consumable):
    """Potion de soin: +20 PV (flat)."""

    def __init__(self) -> None:
        super().__init__("potion_hp_s", "Petite potion de soin", "Restaure 20 PV.", max_stack=10)

    def on_use(self, user: "Entity", ctx: Optional["CombatContext"] = None) -> list["CombatEvent"]:
        healed = user.heal_hp(20)
        return [CombatEvent(text=f"{user.name} boit une potion et récupère {healed} PV.", tag="use_potion_hp", data={"amount": healed})]


class SmallSpiritPotion(Consumable):
    """Potion d’esprit: +10 SP (flat)."""

    def __init__(self) -> None:
        super().__init__("potion_sp_s", "Petite potion d’esprit", "Restaure 10 SP.", max_stack=10)

    def on_use(self, user: "Entity", ctx: Optional["CombatContext"] = None) -> list["CombatEvent"]:
        restored = user.heal_sp(10)
        return [CombatEvent(text=f"{user.name} retrouve {restored} SP.", tag="use_potion_sp", data={"amount": restored})]


# Petite “banque” pour créer des items depuis un id si besoin
ITEM_FACTORY = {
    "potion_hp_s": SmallHealingPotion,
    "potion_sp_s": SmallSpiritPotion,
}

def make_item(item_id: str):
    cls = ITEM_FACTORY.get(item_id)
    if not cls:
        raise KeyError(f"Unknown item id: {item_id}")
    return cls()

BASE_EQUIP = {
    "base_weapon": None,
    "base_armor": None,
    "base_artifact": None
}