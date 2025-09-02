from __future__ import annotations
"""Base des items du jeu (agnostique de l'affichage)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.entity import Entity
    from core.combat import CombatEvent, CombatContext


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
    name: str
    description: str = ""
    stackable: bool = True
    max_stack: int = 99


class Consumable(Item):
    """Consommable basique (ex: potion). Définit un hook on_use(user, ctx)."""

    def __init__(self, item_id: str, name: str, description: str = "", *, max_stack: int = 99) -> None:
        super().__init__(item_id=item_id, name=name, description=description, stackable=True, max_stack=max_stack)

    def on_use(self, user: Entity, ctx: CombatContext | None = None) -> list[CombatEvent]:
        """Applique l'effet et renvoie des events (peut être vide)."""
        raise NotImplementedError("Consumable.on_use must be implemented by subclasses")
