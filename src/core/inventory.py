from __future__ import annotations
"""Inventaire minimal: piles d'items + liste d'équipements, capacité en *slots*.

- Un *slot* = 1 pile stackable (Item) **ou** 1 équipement (Equipment).
- Les équipements ne sont pas stackables (durabilité individuelle).
- API pure logique (aucun I/O), pensée pour être appelée depuis GameLoop/IO.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias

from core.item import Item, Consumable

if TYPE_CHECKING:
    from core.equipment import Equipment
    from core.entity import Entity
    from core.player import Player
    from core.combat import CombatEvent, CombatContext

Slot: TypeAlias = Literal["primary", "skill", "utility"]
VALID_SLOT = ("primary", "skill", "utility")


@dataclass
class InventoryStack:
    item: Item
    qty: int


class Inventory:
    """Inventaire à capacité *en slots*.

    Exemple: capacity=12 → au total 12 piles/équipements combinés.
    """

    def __init__(self, capacity: int = 12) -> None:
        self.capacity: int = max(1, int(capacity))
        self._stacks: dict[str, list[InventoryStack]] = {}  # item_id -> [stacks...]
        self._equipment: list[Equipment] = []

    # ---- Introspection / état ----

    @property
    def slots_used(self) -> int:
        return len(self._equipment) + sum(len(v) for v in self._stacks.values())

    @property
    def slots_free(self) -> int:
        return max(0, self.capacity - self.slots_used)

    def list_summary(self) -> list[dict]:
        """Résumé lisible pour l'UI (pas d’I/O ici)."""
        rows: list[dict] = []
        for stacks in self._stacks.values():
            for s in stacks:
                rows.append({"kind": "item", "id": s.item.item_id, "name": s.item.name, "qty": s.qty})
        for eq in self._equipment:
            rows.append({"kind": "equip", "id": getattr(eq, "name", "???"), "name": getattr(eq, "name", "???"), "qty": 1})
        return rows

    # ---- Ajout / retrait d'items ----

    def add_item(self, item: Item, qty: int = 1) -> int:
        """Ajoute un *Item* stackable. Retourne la quantité réellement ajoutée (peut être < qty si manque de slots)."""
        qty = max(0, int(qty))
        if qty == 0:
            return 0

        if not item.stackable:
            # Par sécurité: on refuse ici; utiliser add_equipment() pour du non-stackable
            return 0

        added = 0
        stacks = self._stacks.setdefault(item.item_id, [])

        # 1) Remplir les piles existantes
        for st in stacks:
            if st.qty >= item.max_stack:
                continue
            can = min(item.max_stack - st.qty, qty - added)
            st.qty += can
            added += can
            if added >= qty:
                return added

        # 2) Créer de nouvelles piles si slots disponibles
        while added < qty and self.slots_free > 0:
            take = min(item.max_stack, qty - added)
            stacks.append(InventoryStack(item=item, qty=take))
            added += take

        return added

    def remove_item(self, item_id: str, qty: int = 1) -> int:
        """Retire jusqu'à qty unités d'un item stackable. Retourne la quantité réellement retirée."""
        qty = max(0, int(qty))
        if qty == 0:
            return 0
        removed = 0
        stacks = self._stacks.get(item_id, [])
        i = 0
        while i < len(stacks) and removed < qty:
            take = min(stacks[i].qty, qty - removed)
            stacks[i].qty -= take
            removed += take
            if stacks[i].qty <= 0:
                stacks.pop(i)
                continue
            i += 1
        if not stacks and item_id in self._stacks:
            del self._stacks[item_id]
        return removed

    def count(self, item_id: str) -> int:
        """Quantité totale d'un item stackable (toutes piles confondues)."""
        return sum(st.qty for st in self._stacks.get(item_id, []))

    # ---- Équipements ----

    def add_equipment(self, equip: Equipment) -> bool:
        """Ajoute un équipement (1 slot)."""
        if self.slots_free <= 0:
            return False
        self._equipment.append(equip)
        return True

    def remove_equipment(self, equip: Equipment) -> bool:
        """Retire un équipement s'il est présent."""
        try:
            self._equipment.remove(equip)
            return True
        except ValueError:
            return False

    def list_equipment(self) -> list[Equipment]:
        return list(self._equipment)

    # ---- Utilisation de consommables ----

    def use_consumable(self, item_id: str, user: Entity, ctx: CombatContext | None = None) -> list[CombatEvent]:
        """Utilise 1 unité d'un consommable si disponible. Retourne les events générés."""
        stacks = self._stacks.get(item_id, [])
        if not stacks:
            return []
        stack = stacks[0]
        item = stack.item
        if not isinstance(item, Consumable):
            return []

        events = item.on_use(user, ctx)
        # Consommer 1 unité *après* exécution (même si pas d'effets concrets)
        self.remove_item(item_id, 1)
        return events

    # ---- (Dé)équiper depuis l’inventaire ----

    def equip_to(self, owner: Player, equip: Equipment, slot: Slot) -> bool:
        """Équipe `equip` (doit être présent dans l’inventaire). Si un objet occupait le slot, il est renvoyé dans l’inventaire.

        Retourne False si pas de place pour récupérer l'ancien équipement.
        """
        if slot not in VALID_SLOT:
            raise ValueError(f"slot invalide {slot}")  
        if equip not in self._equipment:
            return False

        current = getattr(owner, slot, None)
        # Vérifier la place si on doit récupérer l'ancien
        if current is not None and self.slots_free <= 0:
            return False

        # Équipe
        owner.equip(equip, slot)  # ton Player.equip(...) appelle on_equip
        self.remove_equipment(equip)

        # Récupérer l'ancien si existait
        if current is not None:
            self.add_equipment(current)
        return True

    def unequip_from(self, owner: Player, slot: Slot) -> bool:
        """Déséquipe le slot -> place l'objet dans l'inventaire (si place)."""
        current = getattr(owner, slot, None)
        if current is None:
            return False
        if self.slots_free <= 0:
            return False
        owner.unequip(slot)  # ton Player.unequip(...) appelle on_unequip
        self.add_equipment(current)
        return True
