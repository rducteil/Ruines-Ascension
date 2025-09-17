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
from typing import Any, Callable
import json
from pathlib import Path
from copy import deepcopy

from core.data_paths import default_data_dirs
from core.attack import Attack
from core.loadout import Loadout
from core.item import Consumable
from core.stats import Stats
from core.player_class import PlayerClass
from content.effects_bank import make_effect
from core.effect_manager import EffectManager
from content.shop_offers import ShopOffer
from core.enemy import Enemy  
from core.equipment import Weapon, Armor, Artifact
from core.equipment_set import EquipmentSet
from core.combat import CombatEvent


# ---------- Helpers JSON ----------

def _read_json_first(path_rel: str) -> dict[str, dict] | None:
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

def load_player_classes(merge_into: dict[str, PlayerClass] | None = None) -> dict[str, PlayerClass]:
    """Charge player_classes.json et retourne/merge un registre {key: PlayerClass}."""
    raw = _read_json_first("player_classes.json")
    if not isinstance(raw, dict):
        return merge_into or {}

    result: dict[str, PlayerClass] = {} if merge_into is None else merge_into
    for key, row in raw.items():
        key = (str(key) or "").strip().lower()
        name = row.get("name", key)
        bonus: dict = row.get("bonus_stats", {})
        bonus_stats = Stats(
            attack=int(bonus.get("attack", 0)),
            defense=int(bonus.get("defense", 0)),
            luck=int(bonus.get("luck", 0)),
        )
        bonus_hp = int(row.get("bonus_hp_max", 0))
        bonus_sp = int(row.get("bonus_sp_max", 0))

        # l'equipement set de base
        base_equip: dict[str, dict] = row.get("base_equip", {})
        base_weapon = Weapon(
            name=base_equip.get("weapon", {}).get("name", "name"),
            durability_max=base_equip.get("weapon", {}).get("durability_max", 0),
            bonus_attack=base_equip.get("weapon", {}).get("bonus_attack", 0),
            description=base_equip.get("weapon", {}).get("description", "")
        )
        base_armor = Armor(
            name=base_equip.get("armor", {}).get("name", "name"),
            durability_max=base_equip.get("armor", {}).get("durability_max", 0),
            bonus_defense=base_equip.get("armor", {}).get("bonus_defense", 0),
            description=base_equip.get("armor", {}).get("description", "")
        )
        base_artifact = Artifact(
            name=base_equip.get("artifact", {}).get("name", "name"),
            durability_max=base_equip.get("artifact", {}).get("durability_max", 0),
            atk_pct=base_equip.get("artifact", {}).get("atk_pct", 0.0),
            def_pct=base_equip.get("artifact", {}).get("def_pct", 0.0),
            lck_pct=base_equip.get("artifact", {}).get("lck_pct", 0.0),
            description=base_equip.get("artifact", {}).get("description", "")
        )
        class_base_equip = EquipmentSet(
            weapon=base_weapon,
            armor=base_armor,
            artifact=base_artifact
        )

        # attaque de classe
        atk_def: dict = row.get("attack")
        class_attack = _attack_from_dict(atk_def)

        result[key] = PlayerClass(
            name=name,
            bonus_stats=bonus_stats,
            bonus_hp_max=bonus_hp,
            bonus_sp_max=bonus_sp,
            class_attack=class_attack,
            class_base_equip=class_base_equip
        )
    return result

# ---------- Attacks & Loadouts ----------

def _attack_from_dict(d: dict) -> Attack:
    """Crée une Attack depuis un dict JSON (supporte 'effects':[{'effect_id', 'duration','potency'}])."""
    d: dict[str, dict] = dict(d)  # shallow copy
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

def load_attacks() -> dict[str, Attack]:
    """Charge attacks.json et retourne un dict {ATTACK_KEY: Attack}."""
    raw = _read_json_first("attacks.json")
    res: dict[str, Attack] = {}
    if isinstance(raw, dict):
        for key, d in raw.items():
            res[key] = _attack_from_dict(d)
    return res

def load_loadouts(attacks_registry: dict[str, Attack]) -> dict[str, Loadout]:
    """Charge loadouts.json et construit {class_key: Loadout} à partir des clés d'attaque."""
    raw = _read_json_first("loadouts.json")
    res: dict[str, Loadout] = {}
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
            from core.combat import CombatEvent
            evs.append(CombatEvent(text="L’objet ne semble rien faire.", tag="use_none"))
        return evs

def load_items() -> dict[str, DataConsumable]:
    """Charge items.json et retourne un factory dict {item_id: callable()->Consumable}."""
    raw = _read_json_first("items.json")
    res: dict[str, Any] = {}
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

def load_shop_offers() -> tuple[list[ShopOffer], dict[str, int]]:
    """Charge shops/offers.json et shops/config.json.

    Retourne (offers, config) où:
      - offers: liste d'objets ShopOffer (kind 'item' / 'class_scroll')
      - config: dict avec 'rest_hp_pct', 'rest_sp_pct', 'repair_cost_per_point'
    """
    offers_raw = _read_json_first("shops/offers.json") or {}
    items_rows = offers_raw.get("items", [])
    class_scroll = offers_raw.get("class_scroll", {"name": "Parchemin de maîtrise", "base_price": 50})

    offers: list[ShopOffer] = []
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

# -------- Ennemis --------

@dataclass
class EnemyBlueprint:
    enemy_id: str
    name: str
    base_stats: Stats
    hp_max: int
    sp_max: int
    attacks: list[Attack]
    attack_weights: list[int]
    scaling: dict
    gold_min: int = 0
    gold_max: int = 0

    def build(self, *, level: int) -> Enemy:
        # applique un scaling simple
        atk = self.base_stats.attack + int(self.scaling.get("attack_per_level", 0) * max(0, level - 1))
        df  = self.base_stats.defense + int(self.scaling.get("defense_per_level", 0) * max(0, level - 1))
        lk  = self.base_stats.luck   # on ne scale pas la luck par défaut
        hp  = self.hp_max + int(self.scaling.get("hp_per_level", 0) * max(0, level - 1))

        e = Enemy(
            name=self.name,
            base_stats=Stats(attack=atk, defense=df, luck=lk),
            base_hp_max=hp,
            base_sp_max=self.sp_max
        )
        # on accroche la liste d'attaques côté ennemi pour que _select_enemy_attack puisse piocher
        setattr(e, "attacks", list(self.attacks))
        setattr(e, "attack_weights", list(self.attack_weights or [1] * max(1, len(self.attacks))))
        setattr(e, "enemy_id", self.enemy_id)
        return e


def load_enemy_blueprints(attacks_registry: dict[str, Attack]) -> dict[str, EnemyBlueprint]:
    """Lit data/enemies/*.json ; chaque .json peut être un dict (1 ennemi) ou une liste d’ennemis."""
    from core.data_paths import default_data_dirs
    from pathlib import Path
    import json

    res: dict[str, EnemyBlueprint] = {}
    for base in default_data_dirs():
        folder = Path(base) / "enemies"
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                rows = raw if isinstance(raw, list) else [raw]
            except Exception:
                continue

            for row in rows:
                try:
                    eid = row["id"]
                    name = row.get("name", eid)
                    bs = row.get("stats", {})
                    base_stats = Stats(
                        attack=int(bs.get("attack", 0)),
                        defense=int(bs.get("defense", 0)),
                        luck=int(bs.get("luck", 0)),
                    )
                    hp = int(row.get("hp_max", 1))
                    sp = int(row.get("sp_max", 0))
                    gold_min = int(row.get("gold_min", 0))
                    gold_max = int(row.get("gold_max", 0))
                    atk_keys: list[str] = list(row.get("attacks", []))
                    atk_objs = [attacks_registry[k] for k in atk_keys if k in attacks_registry]
                    weights = list(row.get("attack_weights", [])) or [1] * max(1, len(atk_objs))
                    scaling = dict(row.get("scaling", {}))
                    res[eid] = EnemyBlueprint(
                        enemy_id=eid, name=name, base_stats=base_stats,
                        hp_max=hp, sp_max=sp, attacks=atk_objs, attack_weights=weights, scaling=scaling, gold_max=gold_max, gold_min=gold_min
                    )
                except Exception:
                    continue
    return res

def load_encounter_tables() -> dict[str, dict[str, list[dict]]]:
    """Lit:
    - soit plusieurs fichiers data/encounters/*.json avec {zone_type, normal, boss}
    - soit un seul fichier 'mob_encounter.json' qui mappe { "RUINS": {...}, "CAVES": {...}, ... }.
    Retourne {zone_name: {"normal":[{enemy_id,weight}], "boss":[...]}}.
    """
    from core.data_paths import default_data_dirs
    from pathlib import Path
    import json

    res: dict[str, dict[str, list[dict]]] = {}
    for base in default_data_dirs():
        folder = Path(base) / "encounters"
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            # format 1: { "zone_type": "...", "normal": [...], "boss": [...] }
            if isinstance(raw, dict) and "zone_type" in raw:
                zname = str(raw.get("zone_type", "")).upper()
                res[zname] = {
                    "normal": list(raw.get("normal", [])),
                    "boss": list(raw.get("boss", [])),
                }
                continue

            # format 2: { "RUINS": {...}, "CAVES": {...}, ... }
            if isinstance(raw, dict):
                for zname, bucket in raw.items():
                    if not isinstance(bucket, dict):
                        continue
                    res[str(zname).upper()] = {
                        "normal": list(bucket.get("normal", [])),
                        "boss": list(bucket.get("boss", [])),
                    }
    return res


# -------- Équipements --------

def load_equipment_zone_index() -> dict[str, dict[str, list[str]]]:
    """Retourne {"weapon": {id:[zones]}, "armor": {...}, "artifact": {...}}."""
    from core.data_paths import default_data_dirs
    from pathlib import Path, PurePath
    import json
    out = {"weapon": {}, "armor": {}, "artifact": {}}
    for base in default_data_dirs():
        eqdir = Path(base) / "equipment"
        if not eqdir.is_dir():
            continue
        for fname, kind in (("weapons.json","weapon"),("armors.json","armor"),("artifacts.json","artifact")):
            p = eqdir / fname
            if not p.exists(): continue
            try:
                rows = json.loads(p.read_text(encoding="utf-8"))
                for r in rows:
                    zones = [z.upper() for z in r.get("zones", [])]
                    out[kind][r["id"]] = zones
            except Exception:
                pass
    return out

def load_equipment_banks() -> tuple[dict[str, Callable[[], Weapon]],
                                    dict[str, Callable[[], Armor]],
                                    dict[str, Callable[[], Artifact]]]:
    """Lit src/data/equipment/*.json et retourne 3 factories {id: ()->instance}."""
    from core.data_paths import default_data_dirs
    from pathlib import Path
    import json

    w_fact: dict[str, Callable[[], Weapon]] = {}
    a_fact: dict[str, Callable[[], Armor]] = {}
    r_fact: dict[str, Callable[[], Artifact]] = {}

    for base in default_data_dirs():
        eqdir = Path(base) / "equipment"
        if not eqdir.is_dir():
            continue

        # weapons
        wpath = eqdir / "weapons.json"
        if wpath.exists():
            try:
                rows = json.loads(wpath.read_text(encoding="utf-8"))
                for row in rows:
                    wid = row["id"]; name = row.get("name", wid)
                    dmax = int(row.get("durability_max", 10))
                    batk = int(row.get("bonus_attack", 0))
                    def _wf(_name=name, _dmax=dmax, _batk=batk):
                        return Weapon(name=_name, durability_max=_dmax, bonus_attack=_batk)
                    w_fact[wid] = _wf
            except Exception:
                pass

        # armors
        apath = eqdir / "armors.json"
        if apath.exists():
            try:
                rows = json.loads(apath.read_text(encoding="utf-8"))
                for row in rows:
                    aid = row["id"]; name = row.get("name", aid)
                    dmax = int(row.get("durability_max", 12))
                    bdef = int(row.get("bonus_defense", 0))
                    def _af(_name=name, _dmax=dmax, _bdef=bdef):
                        return Armor(name=_name, durability_max=_dmax, bonus_defense=_bdef)
                    a_fact[aid] = _af
            except Exception:
                pass

        # artifacts
        rpath = eqdir / "artifacts.json"
        if rpath.exists():
            try:
                rows = json.loads(rpath.read_text(encoding="utf-8"))
                for row in rows:
                    rid = row["id"]; name = row.get("name", rid)
                    dmax = int(row.get("durability_max", 8))
                    atk_pct = float(row.get("atk_pct", 0.0))
                    def_pct = float(row.get("def_pct", 0.0))
                    def _rf(_name=name, _dmax=dmax, _ap=atk_pct, _dp=def_pct):
                        return Artifact(name=_name, durability_max=_dmax, atk_pct=_ap, def_pct=_dp)
                    r_fact[rid] = _rf
            except Exception:
                pass

    return w_fact, a_fact, r_fact