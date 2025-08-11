from core.stats import Stats
from core.settings import *
from core.resource import Resource
from core.resource_modifier import ResourceModifier

class Entity:
    def __init__(self, name: str, base_stats: Stats, base_hp_max: int, base_sp_max: int):
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

    def heal_hp(self, amount: int): return self.hp_res.add(amount)
    def heal_sp(self, amount: int): return self.sp_res.add(amount)

    def take_damage(self, amount: int): return self.hp_res.remove(amount)
    def spend_sp(self, cost: int):
        if self.sp_res.current >= cost:
            self.sp_res.remove(cost)
            return True
        return False
    def restore_all(self):
        self.hp_res.current = self.hp_res.maximum
        self.sp_res.current = self.sp_res.maximum
        
    def is_alive(self):
        return self.hp > 0
    
    def __str__(self):
        return f"Health : {self.hp}/{self.max_hp}\n", f"ATK : {self.base_stats.attack}", f"DEF : {self.base_stats.defense}", f"LCK : {self.base_stats.luck}"
