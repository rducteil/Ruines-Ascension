from __future__ import annotations
"""
Point d'entrée unique pour charger toutes les données du jeu et offrir des utilitaires.

- GameData.load(strict_validate=False)  -> charge tout + (optionnel) valide
- GameData.validate()                   -> renvoie un Report (data_validate)
- Helpers: make_enemy(...), random_enemy_id(...), make_weapon(...), etc.

Ce module s'appuie sur:
- core.data_loader  (chargement JSON -> objets/factories)
- core.data_validate (validation globale)
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any
import random

from core.attack import Attack
from core.loadout import Loadout
from core.player_class import PlayerClass
from core.item import Item
from core.equipment import Weapon, Armor, Artifact
from core.enemy import Enemy
from content.shop_offers import ShopOffer

from core.data_loader import (
    load_attacks,
    load_loadouts,
    load_player_classes,
    load_items,
    load_shop_offers,
    load_enemy_blueprints,
    load_encounter_tables,
    load_equipment_banks,
    load_equipment_zone_index,
    EnemyBlueprint,
)
from core.data_validate import validate_all, Report


# ---------- Exceptions ----------

class DataValidationError(RuntimeError):
    """Soulevée si strict_validate=True et que la validation échoue."""

    def __init__(self, report: Report):
        self.report = report
        super().__init__(self._fmt())

    def _fmt(self) -> str:
        lines = []
        lines.append("Data validation failed:")
        for e in self.report.errors:
            lines.append(f"  - {e}")
        for w in self.report.warnings:
            lines.append(f"  [warn] {w}")
        return "\n".join(lines)


# ---------- Conteneur principal ----------

@dataclass
class GameData:
    # registres de contenu
    attacks: Dict[str, Attack] = field(default_factory=dict)
    loadouts: Dict[str, Loadout] = field(default_factory=dict)
    player_classes: Dict[str, PlayerClass] = field(default_factory=dict)

    # items consommables (factories)
    item_factories: Dict[str, Callable[[], Item]] = field(default_factory=dict)

    # shop
    shop_offers: List[ShopOffer] = field(default_factory=list)
    shop_config: Dict[str, int] = field(default_factory=dict)

    # ennemis & rencontres
    enemy_blueprints: Dict[str, EnemyBlueprint] = field(default_factory=dict)
    encounters: Dict[str, Dict[str, List[Dict[str, Any]]]] = field(default_factory=dict)

    # équipement (factories) + index zones -> ids
    weapon_factories: Dict[str, Callable[[], Weapon]] = field(default_factory=dict)
    armor_factories: Dict[str, Callable[[], Armor]] = field(default_factory=dict)
    artifact_factories: Dict[str, Callable[[], Artifact]] = field(default_factory=dict)
    equipment_zone_index: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    # ---------- Construction / chargement ----------

    @classmethod
    def load(cls, *, strict_validate: bool = False) -> "GameData":
        """
        Charge toutes les banques depuis src/data (ou dossiers utilisateur),
        construit les objets et retourne une instance GameData prête à l'emploi.
        Si strict_validate=True, lance une validation et lève DataValidationError si KO.
        """
        # 1) bases nécessaires pour le reste
        attacks = load_attacks()
        loadouts = load_loadouts(attacks)
        player_classes = load_player_classes()

        # 2) items + shop
        item_factories = load_items()
        offers, shop_cfg = load_shop_offers()

        # 3) ennemis / rencontres
        enemy_blueprints = load_enemy_blueprints(attacks)
        encounters = load_encounter_tables()

        # 4) équipements
        w_bank, a_bank, r_bank = load_equipment_banks()
        eq_index = load_equipment_zone_index()

        gd = cls(
            attacks=attacks,
            loadouts=loadouts,
            player_classes=player_classes,
            item_factories=item_factories,
            shop_offers=offers,
            shop_config=shop_cfg,
            enemy_blueprints=enemy_blueprints,
            encounters=encounters,
            weapon_factories=w_bank,
            armor_factories=a_bank,
            artifact_factories=r_bank,
            equipment_zone_index=eq_index,
        )

        if strict_validate:
            rep = validate_all(verbose=False)
            if not rep.ok():
                raise DataValidationError(rep)
        return gd

    # ---------- Validation ----------

    @staticmethod
    def validate(verbose: bool = True) -> Report:
        """Exécute la validation globale et renvoie le Report."""
        return validate_all(verbose=verbose)

    # ---------- Helpers: Ennemis / Rencontres ----------

    def random_enemy_id(
        self,
        zone: str,
        bucket: str = "normal",
        *,
        rng: Optional[random.Random] = None,
    ) -> Optional[str]:
        """
        Retourne un enemy_id aléatoire pour une zone donnée, pondéré par 'weight'.
        bucket ∈ {'normal', 'boss'}
        """
        rng = rng or random.Random()
        rows = self.encounters.get(zone.upper(), {}).get(bucket, [])
        if not rows:
            return None
        weights = [max(1, int(r.get("weight", 1))) for r in rows]
        choice = rng.choices(rows, weights=weights, k=1)[0]
        return str(choice.get("enemy_id"))

    def make_enemy(self, enemy_id: str, *, level: int) -> Optional[Enemy]:
        """Construit un ennemi depuis son blueprint et un niveau."""
        bp = self.enemy_blueprints.get(enemy_id)
        if not bp:
            return None
        return bp.build(level=level)

    def spawn_random_enemy(
        self, zone: str, *, level: int, bucket: str = "normal", rng: Optional[random.Random] = None
    ) -> Optional[Enemy]:
        """Sélectionne un enemy_id pour la zone, puis instancie l'Enemy correspondant."""
        eid = self.random_enemy_id(zone, bucket=bucket, rng=rng)
        return self.make_enemy(eid, level=level) if eid else None

    # ---------- Helpers: Équipement ----------

    def make_weapon(self, wid: str) -> Optional[Weapon]:
        fac = self.weapon_factories.get(wid)
        return fac() if fac else None

    def make_armor(self, aid: str) -> Optional[Armor]:
        fac = self.armor_factories.get(aid)
        return fac() if fac else None

    def make_artifact(self, rid: str) -> Optional[Artifact]:
        fac = self.artifact_factories.get(rid)
        return fac() if fac else None

    def equipment_ids_for_zone(self, zone: str) -> Dict[str, List[str]]:
        """Retourne les ids d’équipement disponibles pour une zone (par type)."""
        zone = zone.upper()
        out: Dict[str, List[str]] = {"weapon": [], "armor": [], "artifact": []}
        for kind, mapping in self.equipment_zone_index.items():
            for eid, zones in mapping.items():
                if zone in zones:
                    out[kind].append(eid)
        return out

    # ---------- Helpers: Items ----------

    def make_item(self, item_id: str) -> Optional[Item]:
        fac = self.item_factories.get(item_id)
        return fac() if fac else None

    # ---------- Helpers: Loadouts / Classes ----------

    def get_class(self, key: str) -> Optional[PlayerClass]:
        return self.player_classes.get(key)

    def get_loadout_for_class(self, class_key: str) -> Optional[Loadout]:
        return self.loadouts.get(class_key)


__all__ = [
    "GameData",
    "DataValidationError",
]
