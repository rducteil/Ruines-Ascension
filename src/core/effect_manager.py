from __future__ import annotations
"""Gestionnaire d'effets persistants (sans modifier Entity).

- Mappe chaque entité vers une liste d'effets actifs.
- Appelle les hooks aux bons moments: on_apply, on_turn_end, on_expire.
- Copie défensive des effets appliqués pour éviter le partage d'instances.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from enum import Enum
from weakref import WeakKeyDictionary
import copy

from core.combat import CombatContext, CombatEvent
from core.effects import Effect
if TYPE_CHECKING:
    from core.entity import Entity


@dataclass
class EffectInstance:
    '''Instance d'effet appliquée à une cible'''
    effect : Effect
    source_name : str | None = None # ex : nom de l'attaque ou de l'arme

class StackPolicy(str, Enum):
    REFRESH = "refresh"  # remet la durée
    STACK   = "stack"    # ajoute une pile
    IGNORE  = "ignore"   # ne rien faire si déjà présent

class EffectManager:
    '''Enregistre, applique et purge les effets par entité'''

    def __init__(self):
        self._active: WeakKeyDictionary[object, list[EffectInstance]] = WeakKeyDictionary()
    
    # --- Query ---
    def get_effects(self, target : Entity) -> list[EffectInstance]:
        return tuple(self._active.get(target, ()))
    
    def _same_kind(self, a: Effect, b: Effect) -> bool:
        # Ajuste le critère si tu ajoutes un champ `id` sur Effect
        return type(a) is type(b) and a.name == b.name
    
    # --- Apply / Remove ---
    def apply(self, target: Entity, effect: Effect, *, source_name: str | None = None, ctx: CombatContext | None = None, policy: StackPolicy = StackPolicy.REFRESH, max_stacks: int):
        '''Ajoute une copie de l'effet à la cible. Appelle optionnellement on_apply s'il existe.'''
        lst = self._active.setdefault(target, [])

        # Gestion de l'existant selon la politique
        if policy != StackPolicy.STACK:
            for inst in lst:
                if self._same_kind(inst.effect, effect):
                    if policy is StackPolicy.REFRESH:
                        inst.effect.duration = effect.duration
                        if ctx is not None:
                            # Optionnel: log/événement de refresh
                            pass
                    return

        if policy is StackPolicy.STACK:
            stacks = [i for i in lst if self._same_kind(i.effect, effect)]
            if len(stacks) >= max_stacks:
                return

        inst = EffectInstance(effect=copy.deepcopy(effect), source_name=source_name)
        lst.append(inst)
        if ctx is not None:
            inst.effect.on_apply(target, ctx)

    def purge_expired(self, target: Entity, ctx: CombatContext | None = None):
        '''Supprime les effets expirés et appelle on_expire s'il existe'''
        lst = self._active.get(target, [])
        keep: list[EffectInstance] = []
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
        """À appeler à la fin du tour du *porteur* (ctx.attacker == target)."""
        for inst in list(self._active.get(target, [])):
            inst.effect.on_turn_end(ctx)
        self.purge_expired(target, ctx)
    
        # --- Diffusion des hooks "on_hit" ---
    def on_hit(self, attacker: Entity, defender: Entity, ctx: CombatContext):
        """À appeler quand une attaque touche: notifie effets des deux côtés."""
        for inst in self._active.get(attacker, []):
            inst.effect.on_hit(ctx)
        for inst in self._active.get(defender, []):
            inst.effect.on_hit(ctx)

    # --- Sauvegarde / Restauration ---
    def snapshot(self, target: Entity) -> list[dict]:
        """Sérialise effets actifs (pour save)."""
        out = []
        for inst in self._active.get(target, []):
            e = inst.effect
            out.append({
                "cls": type(e).__name__,
                "name": e.name,
                "duration": e.duration,
                "potency": e.potency,
                "source": inst.source_name,
            })
        return out

    def restore(self, target: Entity, rows: list[dict], registry: dict, ctx: CombatContext | None = None):
        """Restaure depuis snapshot. `registry` mappe 'cls' -> constructeur."""
        for r in rows:
            ctor = registry.get(r["cls"])
            if not ctor:
                continue
            eff = ctor(r["name"], int(r["duration"]), int(r["potency"]))
            self.apply(target, eff, source_name=r.get("source"), ctx=ctx)
