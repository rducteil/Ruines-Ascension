from __future__ import annotations
"""Entity de base: stats + ressources + API métier (dégâts, soins, SP).

- Pas d'I/O ici.
- Dépend de: core.stats, core.resource
"""

from core.stats import Stats
from core.resource import Resource


class Entity:
    """
        Entity de base: stats + ressources + API métier (dégâts, soins, SP)
        init: name, base_stats, base_hp_max -> hp_res/hp/max_hp, base_sp_max -> sp_res/sp/sp_max
    """
    def __init__(self, 
                 name: str, 
                 base_stats: Stats, 
                 base_hp_max: int, 
                 base_sp_max: int
                 ):
        self.name = name
        self.base_stats = base_stats
        self.hp_res = Resource(current=base_hp_max, maximum=base_hp_max)
        self.sp_res = Resource(current=base_sp_max, maximum=base_sp_max)

    @property
    def hp(self): return self.hp_res.current
    @property
    def max_hp(self): return self.hp_res.maximum
    @property
    def sp(self): return self.hp_res.current
    @property
    def max_sp(self): return self.sp_res.maximum

    def heal_hp(self, amount: int): 
        return self.hp_res.add(amount)
    def heal_sp(self, amount: int): 
        return self.sp_res.add(amount)
    def restore_all(self):
        self.hp_res.current = self.hp_res.maximum
        self.sp_res.current = self.sp_res.maximum

    def take_damage(self, amount: int): 
        dmg = max(0, int(amount))
        self.hp_res.remove(dmg)
        return dmg
    def spend_sp(self, cost: int):
        c = max(0, int(cost))
        if self.sp_res.current < c: 
            return False
        self.sp_res.remove(c) 
        return True
    
        
    def is_alive(self):
        return self.hp > 0
    
    def __str__(self):
        return f"HP : {self.hp}/{self.max_hp}\n", f"STA : {self.sp}/{self.max_sp}\n", f"ATK : {self.base_stats.attack}", f"DEF : {self.base_stats.defense}", f"LCK : {self.base_stats.luck}"
