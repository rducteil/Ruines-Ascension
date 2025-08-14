from __future__ import annotations
"""Gestionnaire d'effets persistants (sans modifier Entity).

- Mappe chaque entité vers une liste d'effets actifs.
- Appelle les hooks aux bons moments: on_apply, on_turn_end, on_expire.
- Copie défensive des effets appliqués pour éviter le partage d'instances.
"""

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING
from weakref import WeakKeyDictionary
import copy

from core.effects import CombatContext, CombatEvent
from core.effects import Effect
if TYPE_CHECKING:
    from core.entity import Entity

@dataclass
class EffectInstance:
    '''Instance d'effet appliquée à une cible'''
    effect : Effect
    source_name : Optional[str] = None # ex : nom de l'attaque ou de l'arme

class EffectManager:
    '''Enregistre, applique et purge les effets par entité'''

    def __init__(self):
        self._active: WeakKeyDictionary[object, List[EffectInstance]] = WeakKeyDictionary()
    

    # --- Query ---
    def get_effects(self, target : Entity) -> List[EffectInstance]:
        return self._active.get(target, [])
    
    # --- Apply / Remove ---
    def apply(self, target: Entity, effect: Effect, *, source_name: Optional[str] = None, ctx: Optional[CombatContext] = None):
        '''Ajoute une copie de l'effet à la cible. Appelle optionnellement on_apply s'il existe.'''
        inst = EffectInstance(effect=copy.deepcopy(effect), source_name=source_name)
        self._active.setdefault(target, []).append(inst)
        if ctx is not None:
            inst.effect.on_apply(target, ctx)

    def purge_expired(self, target: Entity, ctx: Optional[CombatContext] = None):
        '''Supprime les effets expirés et appelle on_expire s'il existe'''
        lst = self._active.get(target, [])
        keep: List[EffectInstance] = []
        for inst in lst:
            if inst.effect.is_expired():
                if ctx is not None:
                    inst.effect.on_expire(target, ctx)
            else:
                keep.append(inst)
        if keep:
            self._active[target] = keep
        elif target in self._active:
            del self._active[target]
    
    # --- Ticks ---
    def on_turn_end(self, target: Entity, ctx: CombatContext):
        '''Faire agir les effets à la fin de SON tour et décrémente leur durée
        
        Convention: ctx.attacker == target (porteur), ctx.defender == opposant
        '''
        for inst in list(self._active.get(target, [])):
            inst.effect.on_turn_end(ctx)
        self.purge_expired(target, ctx)
