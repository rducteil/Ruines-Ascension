from __future__ import annotations
"""Base des items du jeu (agnostique de l'affichage)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias, Literal

from core.combat import CombatEvent, CombatContext
if TYPE_CHECKING:
    from core.entity import Entity


Slot: TypeAlias = Literal["recovery", "boost", "equipment"]
VALID_SLOT = ("recovery", "boost", "equipment")

@dataclass
class Item:
    """Item générique.

    Attributs:
      - item_id: identifiant unique (ex: "potion_hp_s")
      - name: nom affichable
      - description: texte libre
      - stackable: peut être empilé (True pour consommables)
      - max_stack: taille max d'une pile
    """
    item_id: str
    kind: Slot
    name: str
    description: str = ""
    stackable: bool = True
    max_stack: int = 99


class Consumable(Item):
    """Consommable basique (ex: potion). Définit un hook on_use(user, ctx)."""

    def __init__(self, kind: Slot, item_id: str, name: str, description: str = "", *, max_stack: int = 99) -> None:
        super().__init__(item_id=item_id, kind=kind, name=name, description=description, stackable=True, max_stack=max_stack)

    def on_use(self, user: Entity, ctx: CombatContext | None = None) -> list[CombatEvent]:
        """Applique l'effet et renvoie des events (peut être vide)."""
        if self.kind not in VALID_SLOT:
            raise ValueError(f"kind invalide {self.kind}")  
        elif self.kind == "recovery":
            return [CombatEvent(text="Vous vous rétablissez", tag="recovery_use", data={"item": self.item_id})]
        elif self.kind == "boost":
            return [CombatEvent(text="Vous vous boostez", tag="boost_use", data={"item": self.item_id})]
        elif self.kind == "equipment":
            return [CombatEvent(text="Vous munissez d'equipement", tag="equip_use", data={"item": self.item_id})]
