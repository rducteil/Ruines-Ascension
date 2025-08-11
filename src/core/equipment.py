from typing import Optional
from core.entity import Entity
from core.resource import Resource

class Equipment:
    def __init__(self, name: str, durability_max: int, description: str = "") -> None:
        self.name: str = name
        self.description: str = description
        self.durability = Resource(current=durability_max, maximum=durability_max)

        self._holder: Optional["Entity"] = None    # porteur courant (Player/Enemy)
        self._bonuses_applied: bool = False        # bonus actifs (si équipé et non cassé)

    # --- état ---
    def is_broken(self) -> bool:
        return self.durability.current <= 0

    @property
    def bonuses_active(self) -> bool:
        """Vrai si les bonus sont effectivement appliqués au porteur."""
        return self._bonuses_applied

    # --- cycle de vie d'équipement ---
    def on_equip(self, entity: "Entity") -> None:
        """Appelé par Player/Enemy quand l'objet est équipé."""
        self._holder = entity
        if not self.is_broken() and not self._bonuses_applied:
            self.apply_bonuses(entity)
            self._bonuses_applied = True

    def on_unequip(self, entity: "Entity") -> None:
        """Appelé par Player/Enemy quand l'objet est déséquipé."""
        if self._bonuses_applied:
            self.remove_bonuses(entity)
            self._bonuses_applied = False
        self._holder = None

    # --- (dé)gradation / réparation ---
    def degrade(self, amount: int = 1) -> bool:
        if amount <= 0:
            return False
        was_broken = self.is_broken()
        self.durability.remove(amount)
        if not was_broken and self.is_broken() and self._holder and self._bonuses_applied:
            self.remove_bonuses(self._holder)
            self._bonuses_applied = False
            return True  # vient de casser
        return False

    def repair(self, amount: int) -> bool:
        if amount <= 0:
            return False
        was_broken = self.is_broken()
        self.durability.add(amount)
        if was_broken and not self.is_broken() and self._holder and not self._bonuses_applied:
            self.apply_bonuses(self._holder)
            self._bonuses_applied = True
            return True  # vient d'être réparé (redevenu fonctionnel)
        return False

    def set_quality(self, new_max: int, keep_ratio: bool = False) -> None:
        """Change la durabilité max. Réactive/désactive les bonus si on traverse 0."""
        new_max = max(0, int(new_max))

        was_broken = self.is_broken()
        self.durability.set_maximum(new_max, preserve_ratio=keep_ratio)
        now_broken = self.is_broken()

        # Si l'état a changé et qu'on a un porteur, (dés)activer les bonus
        if self._holder:
            if was_broken and not now_broken and not self._bonuses_applied:
                self.apply_bonuses(self._holder)
                self._bonuses_applied = True
            elif not was_broken and now_broken and self._bonuses_applied:
                self.remove_bonuses(self._holder)
                self._bonuses_applied = False


    # --- hooks à surcharger ---
    def apply_bonuses(self, entity: "Entity") -> None:
        """Applique les bonus de l'objet (override dans les sous-classes)."""
        pass

    def remove_bonuses(self, entity: "Entity") -> None:
        """Retire les bonus de l'objet (override dans les sous-classes)."""
        pass

    # --- helpers UI/log ---
    def get_info(self) -> str:
        state = "cassé" if self.is_broken() else "ok"
        return f"{self.name} [{state}] ({self.durability_current}/{self.durability_max})"