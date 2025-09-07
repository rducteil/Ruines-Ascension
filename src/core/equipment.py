from __future__ import annotations
"""Base des objets équipables: durabilité, (dés)activation des bonus, hooks.

Règles:
- À 0 de durabilité → cassé: l'objet reste équipé mais ses bonus sont désactivés.
- Si réparé (>0) et qu'il est équipé → bonus réappliqués automatiquement.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from core.resource import Resource
if TYPE_CHECKING:
    from core.entity import Entity
    from core.attack import Attack
    from core.combat import CombatContext
    from core.effects import StatPercentMod


class Equipment:
    '''
        Equipement: equip/un_equip, repair/degrade et gère l'application et le retrait des bonus
        init: name, durability, description, _holder, _bonuses_applied    
    '''
    def __init__(self,
                 name: str,
                 durability_max: int,
                 description: str = "",
                 _holder: Optional[Entity] = None,
                 _bonuses_applied: bool = False
                ):
        self.name = name
        self.durability = Resource(current=durability_max, maximum=durability_max)
        self.description = description
        self._holder = _holder
        self._bonuses_applied = _bonuses_applied    

    # --- état ---
    def is_broken(self) -> bool:
        return self.durability.current <= 0

    @property
    def bonuses_active(self) -> bool:
        """Vrai si les bonus sont effectivement appliqués au porteur."""
        return (self._holder is not None) and (not self.is_broken()) and self._bonuses_applied

    # --- cycle de vie d'équipement ---
    def on_equip(self, entity: Entity) -> None:
        """Appelé par Player quand l'objet est équipé."""
        self._holder = entity
        if not self.is_broken():
            self.apply_bonuses(entity)      # bonus appliqué en fonction du type d'équipement
            self._bonuses_applied = True
        else:
            self._bonuses_applied = False

    def on_unequip(self, entity: Entity) -> None:
        """Appelé par Player quand l'objet est déséquipé."""
        if self._bonuses_applied:
            self.remove_bonuses(entity)
        self._bonuses_applied = False
        self._holder = None

    # --- (dé)gradation / réparation ---
    def degrade(self, amount: int = 1) -> bool:
        '''Baisse la durabilité. Retourne True si l'objet vient de se casser.'''
        if amount <= 0 or self.is_broken():
            return False
        before = self.durability.current
        self.durability.remove(amount)
        just_broke = (before > 0 and self.durability.current == 0)
        if just_broke and self._holder is not None and self._bonuses_applied:
            # Désactiver les bonus
            self.remove_bonuses(self._holder)
            self._bonuses_applied = False
        return just_broke

    def repair(self, amount: int) -> bool:
        '''Répare. Retourne True si l'objet redevient fonctionnel (0 -> >0)'''
        if amount <= 0:
            return False
        before = self.durability.current
        self.durability.add(amount)
        became_functional = (before == 0 and self.durability.current > 0)
        if became_functional and self._holder is not None and not self._bonuses_applied:
            # Réactiver les bonus
            self.apply_bonuses(self._holder)
            self._bonuses_applied = True
        return became_functional

    def set_quality(self, new_max: int, keep_ratio: bool = False) -> None:
        """Change la durabilité max. Réactive/désactive les bonus si on traverse 0."""
        was_broken = self.is_broken()
        self.durability.set_maximum(new_max=new_max, preserve_ratio=keep_ratio)
        now_broken = self.is_broken()

        if was_broken and not now_broken:
            # Si redevenu fonctionnel grâce à une hausse de max -> réactive bonus
            if self._holder is not None and not self._bonuses_applied:
                self.apply_bonuses(self._holder)
                self._bonuses_applied = True
        elif not was_broken and now_broken:
            # Si devenu cassé parce qu'on a réduit max -> désactiver bonus
            if self._holder is not None and self.bonuses_active:
                self.remove_bonuses(self._holder)
                self._bonuses_applied = False


    # --- hooks à surcharger ---
    def apply_bonuses(self, entity: Entity) -> None:
        """Applique les bonus de l'objet (override dans les sous-classes)."""
        pass

    def remove_bonuses(self, entity: Entity) -> None:
        """Retire les bonus de l'objet (override dans les sous-classes)."""
        pass

    # --- helpers UI/log ---
    def get_info(self) -> str:
        state = "cassé" if self.is_broken() else "ok"
        return f"{self.name} [{state}] ({self.durability.current}/{self.durability.maximum})"


class Weapon(Equipment):
    """Weapon: bonus plats (ATK), usure à l’usage et attaques spéciales optionelles."""

    def __init__(self, 
                 name: str, 
                 durability_max: int, 
                 bonus_attack: int = 0, 
                 special_attacks: list[Attack] | None = None, 
                 description: str = ""):
        super().__init__(name=name, durability_max=durability_max, description=description)
        self.bonus_attack: int = int(bonus_attack)
        self.special_attacks: list[Attack] = list(special_attacks or [])

    def get_available_attacks(self) -> list[Attack]:
        """Attaques spéciales offertes par l'arme (optionnel)."""
        return list(self.special_attacks)

    # --- stat bonuses ---
    def apply_bonuses(self, entity: Entity) -> None:
        """Apply the weapon's stat bonuses to the holder."""
        entity.base_stats.attack += self.bonus_attack

    def remove_bonuses(self, entity: Entity) -> None:
        """Remove the weapon's stat bonuses from the holder."""
        entity.base_stats.attack -= self.bonus_attack

    # --- usure ---
    def on_after_attack(self, ctx: CombatContext) -> None:
        '''Hook appelé par le moteur après l'attaque du porteur'''
        self.degrade(1)

class Armor(Equipment):
    """Armor: bonus plats (DEF), usure quand on encaisse des dégâts."""

    def __init__(self, 
                 name: str, 
                 durability_max: int,
                 bonus_defense: int = 0, 
                 description: str = "") -> None:
        super().__init__(name=name, durability_max=durability_max, description=description)
        self.bonus_defense: int = int(bonus_defense)

    

    # --- stat bonuses ---
    def apply_bonuses(self, entity: Entity) -> None:
        entity.base_stats.defense += self.bonus_defense

    def remove_bonuses(self, entity: Entity) -> None:
        entity.base_stats.defense -= self.bonus_defense

    # --- usure ---
    def on_after_hit(self, ctx: CombatContext, damage_taken: int) -> None:
        if damage_taken > 0:
            self.degrade(1)

class Artifact(Equipment):
    """A versatile equippable that applies several flat stat bonuses."""

    def __init__(self, 
                 name: str, 
                 durability_max: int, 
                 atk_pct=0.0, 
                 def_pct=0.0, 
                 lck_pct=0.0, 
                 description: str = ""):
        super().__init__(name=name, durability_max=durability_max, description=description)
        self.atk_pct = int(atk_pct)
        self.def_pct = int(def_pct)
        self.lck_pct = int(lck_pct)

    # --- stat bonuses ---
    def apply_bonuses(self, entity: Entity):
        pass

    def remove_bonuses(self, entity: Entity):
        pass
    
    def stat_percent_mod(self) -> StatPercentMod:
        if self.is_broken():
            return StatPercentMod(
                attack_pct=0.0,
                defense_pct=0.0,
                luck_pct=0.0
            )
        return StatPercentMod(
            attack_pct=self.atk_pct,
            defense_pct=self.def_pct,
            luck_pct=self.lck_pct
        )

    def on_turn_end(self, ctx: CombatContext) -> None:
        pass