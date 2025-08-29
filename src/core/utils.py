from typing import Iterable, TYPE_CHECKING
from core.effects import ResourceModifier

if TYPE_CHECKING:
    from core.entity import Entity

def clamp(n, lo, hi):
    if n < lo:
        return lo
    elif n > hi:
        return hi
    else:
        return n
    
