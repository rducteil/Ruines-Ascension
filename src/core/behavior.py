from __future__ import annotations
from typing import Sequence, Protocol, TYPE_CHECKING

from core.attack import Attack
from random import Random
if TYPE_CHECKING:
    from core.enemy import Enemy
    from core.player import Player



class EnemyBehavior(Protocol):
    def choose(self, *, enemy, player, attacks: Sequence[Attack], rng) -> Attack: ...

class Aggressive:
    def choose(self, *, enemy: Enemy, player: Player, attacks: Sequence[Attack], rng: Random):
        """Chosit l'attaque avec le meilleur "potentiel brut" (base + var + ATK - DEF), si SP suffisant"""
        feasible = [a for a in attacks if enemy.sp >= a.cost]
        pool = feasible or attacks or [Attack(name="Coup maladroit", base_damage=4, variance=2)]
        best = max(pool, key=lambda a: (a.base_damage + a.variance + enemy.base_stats.attack - player.base_stats.defense, a.cost))
        return best
    
class Cautious:
    def choose(self, *, enemy: Enemy, player: Player, attacks: Sequence[Attack], rng: Random):
        """Chosit l'attaque au coût faible quand HP/SP bas"""
        feasible = [a for a in attacks if enemy.sp >= a.cost] or attacks
        key = lambda a: (a.cost, -(a.base_damage + a.variance))
        return min(feasible, key=key)
    
class Caster:
    def choose(self, *, enemy: Enemy, player: Player, attacks: Sequence[Attack], rng: Random):
        """Choisit les attaques à coût SP si possible, sinon fallback"""
        sp_attacks = [a for a in attacks if a.cost > 0 and enemy.sp >= a.cost]
        if sp_attacks:
            return rng.choice(sp_attacks)
        feasible = [a for a in attacks if enemy.sp >= a.cost] or attacks
        return rng.choice(feasible)
    
class Balanced:
    def choose(self, *, enemy: Enemy, player: Player, attacks: Sequence[Attack], rng: Random):
        """Mélange pondéré par poids existants"""
        ws = getattr(enemy, "attack_weights", [1]*len(attacks)) if attacks else []
        if attacks and ws:
            total = sum(ws); r = rng.uniform(0, total); acc = 0
            for atk, w in zip(attacks, ws):
                acc += w
                if r <= acc:
                    return atk
        return attacks[0] if attacks else Attack(name="Coup maladroit", base_damage=4, variance=2)

BEHAVIOR_REGISTRY = {
    "aggressive": Aggressive,
    "cautious":   Cautious,
    "caster":     Caster,
    "balanced":   Balanced,
}