from typing import Optional
from core.entity import Entity
from core.stats import Stats


class Enemy(Entity):
    """Non-player combatant with optional behavior tag."""

    def __init__(self, name: str, base_stats: Stats, base_hp_max: int, base_sp_max: int = 0, behavior: Optional[str] = None):
        super().__init__(name=name, base_stats=base_stats, base_hp_max=base_hp_max, base_sp_max=base_sp_max)
        self.behavior: Optional[str] = behavior  # e.g., "aggressif", "défensif"
        self.effect: Optional[object] = None

    def choose_action(self) -> str:
        """Very simple placeholder AI.
        TODO: Replace with a proper action selection (weights, cooldowns, states).
        """
        return "basic_attack"

    # Factory helpers for tests/demo
    @staticmethod
    def training_dummy() -> "Enemy":
        from core.stats import Stats
        return Enemy(name="Poupée d'entraînement", base_stats=Stats(attack=1, defense=0, speed=0), base_hp_max=30)
    
