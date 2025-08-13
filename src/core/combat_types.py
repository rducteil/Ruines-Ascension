from __future__ import annotations
"""Types neutres pour le combat: événements, contexte, résultat."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, TYPE_CHECKING
if TYPE_CHECKING:
    from core.entity import Entity

@dataclass
class CombatEvent:
    """Un message d'événement + tag et data optionnelles pour l'UI."""
    text: str
    tag: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@dataclass
class CombatResult:
    """Résultat d'une résolution d'attaque (un tour)."""
    events: List[CombatEvent]
    attacker_alive: bool
    defender_alive: bool
    damage_dealt: int
    was_crit: bool

@dataclass
class CombatContext:
    """Contexte minimal passé aux hooks d'équipement/effets."""
    attacker: "Entity"
    defender: "Entity"
    events: List[CombatEvent]
    damage_dealt: int = 0
    was_crit: bool = False