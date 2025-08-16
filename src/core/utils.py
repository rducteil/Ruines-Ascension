from typing import Iterable, TYPE_CHECKING
from core.modifier import ResourceModifier

if TYPE_CHECKING:
    from core.entity import Entity

def clamp(n, lo, hi):
    if n < lo:
        return lo
    elif n > hi:
        return hi
    else:
        return n
    
def apply_resource_mods(entity: "Entity", 
                        base_hp_max: int, 
                        base_sp_max: int, 
                        mods: Iterable[ResourceModifier], 
                        preserve_ratio: bool = True):
    hp_pct = sum(m.hp_max_pct for m in mods)
    hp_flat = sum(m.hp_max_flat for m in mods)
    sp_pct = sum(m.sp_max_pct for m in mods)
    sp_flat = sum(m.sp_max_flat for m in mods)

    new_hp_max = int(round(base_hp_max * (1.0+hp_pct))) + hp_flat
    new_sp_max = int(round(base_sp_max * (1.0+sp_pct))) + sp_flat

    entity.hp_res.set_maximum(new_hp_max, preserve_ratio=preserve_ratio)
    entity.sp_res.set_maximum(new_sp_max, preserve_ratio=preserve_ratio)