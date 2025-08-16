from dataclasses import dataclass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.utils import clamp

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