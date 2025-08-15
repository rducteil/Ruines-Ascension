from __future__ import annotations
"""Loaders JSON → objets du core + fusion dans les registres existants.

Fichiers attendus (dans src/data/ ou mods/env):
- player_classes.json           (dict)
- attacks.json                  (dict)
- loadouts.json                 (dict)
- items.json                    (list)
- shops/offers.json             (dict)
- shops/config.json             (dict)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import json
from pathlib import Path
from copy import deepcopy

from core.data_paths import default_data_dirs
from core.attack import Attack
from core.loadout import Loadout
from core.item import Consumable, Item
from core.stats import Stats
from core.player_class import PlayerClass
from content.effects_bank import make_effect
from content.shop_offers import ShopOffer  # on garde le type existant

# ---------- Helpers JSON ----------

def _read_json_first(path_rel: str) -> Optional[Any]:
    """Lit le premier JSON trouvé pour path_rel depuis la liste de répertoires de données."""
    for base in default_data_dirs():
        p = base / Path(path_rel)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None

# ---------- Player classes ----------

def load_player_classes(merge_into: Optional[Dict[str, PlayerClass]] = None) -> Dict[str, PlayerClass]:
    """Charge player_classes.json et retourne/merge un registre {key: PlayerClass}."""
    raw = _read_json_first("player_classes.json")
    if not isinstance(raw, dict):
        return merge_into or {}

    result: Dict[str, PlayerClass] = {} if merge_into is None else merge_into
    for key, row in raw.items():
        name = row.get("name", key.capitalize())
        bonus = row.get("bonus_stats", {})
        bonus_stats = Stats(
            attack=int(bonus.get("attack", 0)),
            defense=int(bonus.get("defense", 0)),
            luck=int(bonus.get("luck", 0)),
        )
        bonus_hp = int(row.get("bonus_hp_max", 0))
        bonus_sp = int(row.get("bonus_sp_max", 0))

        # attaque de classe optionnelle
        atk_def = row.get("attack")
        class_attack = None
        if isinstance(atk_def, dict):
            class_attack = _attack_from_dict(atk_def)

        result[key] = PlayerClass(
            key=key,
            display_name=name,
            bonus_stats=bonus_stats,
            bonus_hp_max=bonus_hp,
            bonus_sp_max=bonus_sp,
            class_attack=class_attack,
        )
    return result

# ---------- Attacks & Loadouts ----------

def _attack_from_dict(d: dict) -> Attack:
    """Crée une Attack depuis un dict JSON (supporte 'effects':[{'effect_id', 'duration','potency'}])."""
    d = dict(d)  # shallow copy
    # convertir effects -> objets Effect
    effs = []
    for e in d.get("effects", []) or []:
        eid = e.get("effect_id")
        dur = int(e.get("duration", 0))
        pot = int(e.get("potency", 0))
        effs.append(make_effect(eid, duration=dur, potency=pot))
    d["effects"] = effs

    # champs connus de Attack (on laisse Python ignorer ceux qu'il ne connaît pas si dataclass strict=False)
    return Attack(
        name=d.get("name", "Attaque"),
        base_damage=int(d.get("base_damage", 0)),
        variance=int(d.get("variance", 0)),
        cost=int(d.get("cost", 0)),
        crit_multiplier=float(d.get("crit_multiplier", 2.0)),
        ignore_defense_pct=float(d.get("ignore_defense_pct", 0.0)),
        true_damage=int(d.get("true_damage", 0)),
        effects=effs,
        # facultatif si tu as ajouté 'target' à Attack
        **({ "target": d["target"] } if "target" in d else {})
    )

def load_attacks() -> Dict[str, Attack]:
    """Charge attacks.json et retourne un dict {ATTACK_KEY: Attack}."""
    raw = _read_json_first("attacks.json")
    res: Dict[str, Attack] = {}
    if isinstance(raw, dict):
        for key, d in raw.items():
            res[key] = _attack_from_dict(d)
    return res

def load_loadouts(attacks_registry: Dict[str, Attack]) -> Dict[str, Loadout]:
    """Charge loadouts.json et construit {class_key: Loadout} à partir des clés d'attaque."""
    raw = _read_json_first("loadouts.json")
    res: Dict[str, Loadout] = {}
    if not isinstance(raw, dict):
        return res
    for class_key, row in raw.items():
        try:
            p = deepcopy(attacks_registry[row["primary"]])
            s = deepcopy(attacks_registry[row["skill"]])
            u = deepcopy(attacks_registry[row["utility"]])
            res[class_key] = Loadout(primary=p, skill=s, utility=u)
        except Exception:
            # clé manquante → on saute
            continue
    return res

# ---------- Items (consommables) & Shop ----------

class DataConsumable(Consumable):
    """Consommable générique dont l'effet est décrit en JSON (champ 'use')."""
    def __init__(self, item_id: str, name: str, description: str, *, max_stack: int, payload: dict) -> None:
        super().__init__(item_id=item_id, name=name, description=description, max_stack=max_stack)
        self._payload = dict(payload or {})

    def on_use(self, user, ctx=None):
        from core.combat_types import CombatEvent
        t = self._payload.get("type")
        evs: list[CombatEvent] = []
        if t == "heal_hp":
            amt = int(self._payload.get("amount", 0))
            healed = user.heal_hp(amt)
            evs.append(CombatEvent(text=f"{user.name} récupère {healed} PV.", tag="use_heal_hp", data={"amount": healed}))
        elif t == "heal_sp":
            amt = int(self._payload.get("amount", 0))
            restored = user.heal_sp(amt)
            evs.append(CombatEvent(text=f"{user.name} récupère {restored} SP.", tag="use_heal_sp", data={"amount": restored}))
        elif t == "apply_effect":
            eid = self._payload.get("effect_id")
            dur = int(self._payload.get("duration", 0))
            pot = int(self._payload.get("potency", 0))
            eff = make_effect(eid, duration=dur, potency=pot)
            # on cible l'utilisateur (buff) par défaut
            from core.effect_manager import EffectManager
            # On suppose que le GameLoop a un EffectManager; si ctx n'existe pas, on applique à sec:
            try:
                # si le ctx est fourni, on applique via manager si dispo sur la boucle
                gm = getattr(ctx, "effect_manager", None) if ctx else None
                if gm is not None and isinstance(gm, EffectManager):
                    gm.apply(user, eff, source_name=f"item:{self.item_id}", ctx=ctx)
                else:
                    # fallback sans manager: déclenche immédiatement on_apply
                    eff.on_apply(user, ctx)
                evs.append(CombatEvent(text=f"{user.name} bénéficie de {eff.name}.", tag="use_apply_effect"))
            except Exception:
                evs.append(CombatEvent(text="L’objet crépite… sans effet notable.", tag="use_unknown"))
        else:
            from core.combat_types import CombatEvent
            evs.append(CombatEvent(text="L’objet ne semble rien faire.", tag="use_none"))
        return evs

def load_items() -> Dict[str, DataConsumable]:
    """Charge items.json et retourne un factory dict {item_id: callable()->Consumable}."""
    raw = _read_json_first("items.json")
    res: Dict[str, Any] = {}
    if isinstance(raw, list):
        for row in raw:
            try:
                item_id = row["item_id"]
                name = row["name"]
                desc = row.get("description", "")
                stackable = bool(row.get("stackable", True))
                max_stack = int(row.get("max_stack", 99))
                use_payload = dict(row.get("use", {}))
                if not stackable:
                    # Pour l’instant, on ne gère que les consommables data-driven
                    continue
                def _factory(_id=item_id, _n=name, _d=desc, _m=max_stack, _p=use_payload):
                    return DataConsumable(item_id=_id, name=_n, description=_d, max_stack=_m, payload=_p)
                res[item_id] = _factory
            except Exception:
                continue
    return res

def load_shop_offers() -> Tuple[List[ShopOffer], Dict[str, int]]:
    """Charge shops/offers.json et shops/config.json.

    Retourne (offers, config) où:
      - offers: liste d'objets ShopOffer (kind 'item' / 'class_scroll')
      - config: dict avec 'rest_hp_pct', 'rest_sp_pct', 'repair_cost_per_point'
    """
    offers_raw = _read_json_first("shops/offers.json") or {}
    items_rows = offers_raw.get("items", [])
    class_scroll = offers_raw.get("class_scroll", {"name": "Parchemin de maîtrise", "base_price": 50})

    offers: List[ShopOffer] = []
    for row in items_rows:
        try:
            offers.append(ShopOffer(kind="item",
                                    name=row["name"],
                                    price=int(row.get("base_price", 10)),
                                    item_id=row["item_id"]))
        except Exception:
            continue
    offers.append(ShopOffer(kind="class_scroll",
                            name=class_scroll.get("name", "Parchemin de maîtrise"),
                            price=int(class_scroll.get("base_price", 50)),
                            class_key=None))  # la classe réelle est injectée à l'usage

    conf_raw = _read_json_first("shops/config.json") or {}
    cfg = {
        "rest_hp_pct": int(conf_raw.get("rest_hp_pct", 30)),
        "rest_sp_pct": int(conf_raw.get("rest_sp_pct", 30)),
        "repair_cost_per_point": int(conf_raw.get("repair_cost_per_point", 2)),
    }
    return offers, cfg
