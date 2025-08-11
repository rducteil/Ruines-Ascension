from dataclasses import dataclass

@dataclass
class ResourceModifier:
    hp_max_flat: int = 0
    hp_max_pct: float = 0.0
    sp_max_flat: int = 0
    sp_max_pct: float = 0.0
    