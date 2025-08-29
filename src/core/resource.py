from dataclasses import dataclass
from typing import TYPE_CHECKING
from core.utils import clamp

if TYPE_CHECKING:
    from core.entity import Entity

@dataclass
class ResourceMaxMods:
    hp_max_pct: float = 0.0
    hp_max_flat: int = 0
    sp_max_pct: float = 0.0
    sp_max_flat: int = 0

@dataclass
class Resource:
    '''Création d'une ressource: current/maximum, add/remove et set_maximum'''
    current: int
    maximum: int

    def add(self, amount: int):
        before = self.current
        self.current = clamp(self.current +  amount, 0, self.maximum)
        return self.current - before
    
    def remove(self, amount: int):
        before = self.current
        self.current = clamp(self.current -  amount, 0, self.maximum)
        return before - self.current
    
    def set_maximum(self, new_max: int, preserve_ratio: bool = True):
        if preserve_ratio and self.maximum > 0:
            ratio = self.current / self.maximum
            self.maximum = max(0, new_max)
            self.current = int(round(self.maximum * ratio))
        else:
            self.maximum = max(0,new_max)
            self.current = min(self.current, self.maximum)

def apply_max_mods(entity: Entity, mods: ResourceMaxMods, preserve_ratio: bool = True):
    hp_pct  = sum(m.hp_max_pct for m in mods)
    hp_flat = sum(m.hp_max_flat for m in mods)
    sp_pct  = sum(m.sp_max_pct for m in mods)
    sp_flat = sum(m.sp_max_flat for m in mods)

    new_hp_max = int(round(entity.hp_res.maximum * (1.0 + hp_pct))) + hp_flat
    new_sp_max = int(round(entity.sp_res.maximum * (1.0 + sp_pct))) + sp_flat

    entity.hp_res.set_maximum(new_hp_max, preserve_ratio=preserve_ratio)
    entity.sp_res.set_maximum(new_sp_max, preserve_ratio=preserve_ratio)