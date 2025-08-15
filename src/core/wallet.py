from __future__ import annotations

class Wallet:
    """Porte-monnaie simple (or)."""
    def __init__(self, gold: int = 0) -> None:
        self._gold = max(0, int(gold))

    @property
    def gold(self) -> int:
        return self._gold

    def add(self, amount: int) -> int:
        amount = int(amount)
        if amount <= 0: return 0
        self._gold += amount
        return amount

    def can_afford(self, amount: int) -> bool:
        return self._gold >= max(0, int(amount))

    def spend(self, amount: int) -> bool:
        amount = int(amount)
        if amount <= 0 or self._gold < amount: return False
        self._gold -= amount
        return True
