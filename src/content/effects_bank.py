from __future__ import annotations
"""Registry d'effets pour les évènements data-driven."""

from core.effects import Effect, AttackBuffEffect, DefenseBuffEffect, LuckBuffEffect, PoisonEffect

def make_effect(effect_id: str, *, duration: int = 0, potency: int = 0) -> list[Effect]:
    effect_id = str(effect_id or "").lower()
    if effect_id == "blessing_atk":
        return [AttackBuffEffect("Bénédiction d'attaque", duration=duration, potency=potency)]
    if effect_id == "ward_def":
        return [DefenseBuffEffect("Protection défensive", duration=duration, potency=potency)]
    if effect_id == "luck_up":
        return [LuckBuffEffect("Chance accrue", duration=duration, potency=potency)]
    if effect_id == "poison":
        return [PoisonEffect("Poison", duration=duration, potency=potency)]
    if effect_id == "blessing":
        # alias générique -> buff atk léger par défaut
        return [AttackBuffEffect("Bénédiction", duration=duration, potency=potency), 
                DefenseBuffEffect("Protection défensive", duration=duration, potency=potency)]
    # fallback : effet neutre (aucun hook) pour éviter un crash
    return [Effect(name=f"Effet inconnu: {effect_id}", duration=duration, potency=potency)]
