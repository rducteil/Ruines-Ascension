"""Tier progression & soft-pity utilities."""

from dataclasses import dataclass
from typing import Tuple
import math
import random
from core.utils import clamp, normalize

PhaseWeights = dict[int, float]

@dataclass
class TierProgression:
    # --- paramètres campagne ---
    band_size: int = 4           # 4 zones par phase
    shop_threshold: float = 0.50 # seuil d’apparition au shop
    pity_window: int = 8         # après 8 combats sans loot “à niveau” -> pity
    pity_min_tier: int = 1
    # cap campagne (T6 réservé aux events)
    campaign_max_tier: int = 5

    # Tableau EXACT (ton image) : par phase 1..4
    PHASE_TABLE: dict[int, PhaseWeights] = None

    def __post_init__(self):
        if self.PHASE_TABLE is None:
            self.PHASE_TABLE = {
                1: {-1: 0.25, 0: 0.60, +1: 0.10, +2: 0.05},
                2: {-1: 0.20, 0: 0.55, +1: 0.18, +2: 0.07},
                3: {-1: 0.10, 0: 0.45, +1: 0.35, +2: 0.10},
                4: {-1: 0.05, 0: 0.25, +1: 0.60, +2: 0.10},
            }

    # ---------- helpers ----------
    def tier_for_level(self, level: int) -> int:
        # 1–4 -> T1 ; 5–8 -> T2 ; etc.
        return ((level - 1) // self.band_size) + 1

    def phase_index(self, level: int) -> int:
        return ((level - 1) % self.band_size) + 1  # 1..4

    # ---------- distributions ----------
    def weights(self, level: int, max_tier: int | None = None) -> dict[int, float]:
        """Retourne {tier: proba} pour le niveau donné, borné dans [1..max_tier]."""
        if max_tier is None:
            max_tier = self.campaign_max_tier
        T = self.tier_for_level(level)
        rel = self.PHASE_TABLE.get(self.phase_index(level), self.PHASE_TABLE[1])

        # on mappe offsets -> tiers; tout ce qui <1 est absorbé en T1;
        # >max_tier absorbé en max_tier; puis on renormalise.
        acc: dict[int, float] = {}
        for off, p in rel.items():
            t = clamp(T + off, 1, max_tier)
            acc[t] = acc.get(t, 0.0) + p
        return normalize(acc)

    def shop_available_tiers(self, level: int, max_tier: int | None = None) -> list[int]:
        w = self.weights(level, max_tier)
        avail = [t for (t, p) in w.items() if p >= self.shop_threshold]
        T = self.tier_for_level(level)
        if T not in avail:
            avail.append(T)
        return sorted(set(avail))

    # ---------- pity anti-malchance ----------
    def should_force_high_tier(self, fights_since_good: int) -> bool:
        return fights_since_good >= self.pity_window

    def choose_tier_with_pity(self, rng: random.Random, level: int,
                              max_tier: int | None = None,
                              fights_since_good: int = 0) -> int:
        w = self.weights(level, max_tier)
        if self.should_force_high_tier(fights_since_good):
            T = self.tier_for_level(level)
            w = {t: p for (t, p) in w.items() if t >= max(T, self.pity_min_tier)}
            w = normalize(w)
        tiers, probs = zip(*sorted(w.items()))
        x, acc = rng.random(), 0.0
        for t, p in zip(tiers, probs):
            acc += p
            if x <= acc:
                return t
        return tiers[-1]
