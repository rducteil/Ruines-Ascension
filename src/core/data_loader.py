from __future__ import annotations
"""
Loaders JSON → objets du core + fusion dans les registres existants.

Fichiers attendus (dans src/data/ ou mods/env):
- player_classes.json           (dict)
- attacks.json                  (dict ou list)
- loadouts.json                 (dict)
- items.json                    (dict ou list)
- shops/offers.json             (dict)
- shops/config.json             (dict)
- enemies/*.json                (dict ou list)
- encounters/*.json             (format zone unique ou mapping {ZONE:{...}})
- equipment/weapons.json        (list)
- equipment/armors.json         (list)
- equipment/artifacts.json      (list)
"""

from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING, Dict, List
import json
from pathlib import Path
from copy import deepcopy
import random

from core.data_paths import default_data_dirs
from core.attack import Attack
from core.loadout import Loadout
from core.item import Consumable, Slot
from core.stats import Stats
from core.player_class import PlayerClass
from core.effects_bank import make_effect
from core.effect_manager import EffectManager
from content.shop_offers import ShopOffer
from core.enemy import Enemy
from core.equipment import Weapon, Armor, Artifact
from core.equipment_set import EquipmentSet
from core.combat import CombatEvent
from core.behavior import BEHAVIOR_REGISTRY

if TYPE_CHECKING:
    from core.player import Player


# ---------- Helpers JSON ----------

def _read_json_first(path_rel: str) -> Any | None:
    """Lit le premier JSON trouvé pour path_rel depuis la liste de répertoires de données."""
    for base in default_data_dirs():
        p = base / Path(path_rel)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def _as_list(rows: Any) -> List[Dict[str, Any]]:
    """Accepte soit liste d'objets, soit dict {id: obj}; retourne toujours une liste avec 'id' normalisé en minuscules."""
    if isinstance(rows, list):
        out: List[Dict[str, Any]] = []
        for r in rows:
            r = dict(r or {})
            rid = r.get("id") or r.get("name")
            if rid:
                r["id"] = str(rid).lower()
            out.append(r)
        return out
    if isinstance(rows, dict):
        out: List[Dict[str, Any]] = []
        for k, v in rows.items():
            r = dict(v or {})
            r["id"] = str(r.get("id") or k).lower()
            out.append(r)
        return out
    return []


def _flatten_effects(effs: Any) -> List:
    """Aplati proprement (Effect | list[Effect] | None) -> list[Effect]."""
    out: List = []
    if effs is None:
        return out
    if isinstance(effs, list):
        for e in effs:
            if isinstance(e, list):
                out.extend([ee for ee in e if ee is not None])
            elif e is not None:
                out.append(e)
    else:
        out.append(effs)
    return out


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

        # équipement de base (optionnel)
        base_equip: dict[str, dict] = row.get("base_equip", {})
        base_weapon = Weapon(
            name=base_equip.get("weapon", {}).get("name", "Arme"),
            durability_max=base_equip.get("weapon", {}).get("durability_max", 0),
            bonus_attack=base_equip.get("weapon", {}).get("bonus_attack", 0),
            description=base_equip.get("weapon", {}).get("description", "")
        )
        base_armor = Armor(
            name=base_equip.get("armor", {}).get("name", "Armure"),
            durability_max=base_equip.get("armor", {}).get("durability_max", 0),
            bonus_defense=base_equip.get("armor", {}).get("bonus_defense", 0),
            description=base_equip.get("armor", {}).get("description", "")
        )
        base_artifact = Artifact(
            name=base_equip.get("artifact", {}).get("name", "Artéfact"),
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
        class_attack = _attack_from_dict(atk_def) if isinstance(atk_def, dict) else None

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

def _attack_from_dict(d: dict | None) -> Attack | None:
    """Crée une Attack depuis un dict JSON (supporte effects sous forme str ou dict {id,duration,potency})."""
    if not isinstance(d, dict):
        return None
    row: dict[str, Any] = dict(d)  # shallow copy

    # Construire une liste plate d'effets
    eff_objs: List = []
    for e in (row.get("effects") or []):
        if isinstance(e, dict):
            eid = e.get("id") or e.get("effect_id") or e.get("name")
            dur = int(e.get("duration", 0))
            pot = int(e.get("potency", 0))
            made = make_effect(str(eid), duration=dur, potency=pot)
        else:
            made = make_effect(str(e), duration=0, potency=0)
        eff_objs.extend(_flatten_effects(made))

    # Champs de Attack (adapter si ta classe a d'autres noms)
    atk = Attack(
        name=row.get("name", "Attaque"),
        base_damage=int(row.get("base_damage", 0)),
        variance=int(row.get("variance", 0)),
        cost=int(row.get("cost", 0)),
        crit_multiplier=float(row.get("crit_multiplier", 2.0)),
        ignore_defense_pct=float(row.get("ignore_defense_pct", 0.0)),
        true_damage=int(row.get("true_damage", 0)),
        effects=eff_objs,
        **({"target": row["target"]} if "target" in row else {})
    )
    dd = row.get("deals_damage", True)
    try:
        dd = bool(dd)
    except Exception:
        dd = True
    setattr(atk, "deals_damage", dd)
    return atk


def load_attacks() -> dict[str, Attack]:
    """
    Charge data/attacks.json et construit un dict {attack_id: Attack}.
    - Accepte JSON dict {id: {...}} ou list [{...}].
    - Garantit que Attack.effects est une liste plate d’Effect.
    - Les ids sont normalisés en minuscules.
    """
    raw = _read_json_first("attacks.json")
    if raw is None:
        return {}

    rows = _as_list(raw)
    attacks: Dict[str, Attack] = {}
    for row in rows:
        rid: str = str(row.get("id") or row.get("name") or "").lower()
        if not rid:
            continue
        atk = _attack_from_dict(row)
        if atk is None:
            continue
        attacks[rid] = atk
    return attacks


def load_loadouts(attacks_registry: dict[str, Attack]) -> dict[str, Loadout]:
    """Charge loadouts.json et construit {class_key_lower: Loadout}."""
    raw = _read_json_first("loadouts.json")
    out: dict[str, Loadout] = {}
    if not isinstance(raw, dict):
        return out

    def _slot(val):
        if val in (None, "", 0, "0", "none", "null"):
            return None
        return deepcopy(attacks_registry[str(val).strip().lower()])

    for class_key, row in raw.items():
        ck = str(class_key).strip().lower()
        try:
            p = _slot(row.get("primary"))
            s = _slot(row.get("skill"))
            u = _slot(row.get("utility"))
            out[ck] = Loadout(primary=p, skill=s, utility=u)
        except KeyError:
            continue
    return out


# ---------- Items (consommables) & Shop ----------

def _infer_kind_from_payload(payload: dict) -> Slot:
    """Mappe le type d'usage JSON vers un Slot valide pour Consumable."""
    t = str(payload.get("type", "")).strip().lower()
    # Soins & purge -> recovery
    if t in ("heal_hp", "heal_sp", "cure_poison"):
        return "recovery"
    # Buffs, effets temporaires, fuite/maintenance -> boost
    if t in ("buff_attack_pct", "apply_effect", "smoke_escape", "repair_equipment"):
        return "boost"
    return "boost"


class DataConsumable(Consumable):
    """Consommable générique dont l'effet est décrit en JSON (champ 'use')."""
    def __init__(self, item_id: str, name: str, description: str,
                 *, max_stack: int, payload: dict, kind: Slot | None = None) -> None:
        k: Slot = kind or _infer_kind_from_payload(payload or {})
        super().__init__(item_id=item_id, name=name, description=description, max_stack=max_stack, kind=k)
        self._payload = dict(payload or {})

    def on_use(self, user: Player, ctx=None):
        t = self._payload.get("type")
        evs: list[CombatEvent] = []
        gm = getattr(ctx, "effect_manager", None) if ctx else None
        rng = getattr(getattr(ctx, "engine", None), "rng", None) if ctx else None
        if gm is None and ctx is not None:
            gm = getattr(ctx, "effects", None)

        if t == "heal_hp":
            amt = int(self._payload.get("amount", 0))
            healed = user.heal_hp(amt)
            evs.append(CombatEvent(text=f"{user.name} récupère {healed} PV.", tag="use_heal_hp", data={"amount": healed}))

        elif t == "heal_sp":
            amt = int(self._payload.get("amount", 0))
            restored = user.heal_sp(amt)
            evs.append(CombatEvent(text=f"{user.name} récupère {restored} SP.", tag="use_heal_sp", data={"amount": restored}))

        elif t == "cure_poison":
            try:
                if isinstance(gm, EffectManager):
                    removed = gm.purge(user, cls_name="PoisonEffect")
                else:
                    removed = 0
                if removed:
                    evs.append(CombatEvent(text=f"{user.name} est purgé du poison.", tag="use_cure_poison"))
                else:
                    evs.append(CombatEvent(text="Aucun poison à purger.", tag="use_cure_poison_none"))
            except Exception:
                evs.append(CombatEvent(text="L’antidote n’a eu aucun effet.", tag="use_cure_poison_error"))

        elif t == "buff_attack_pct":
            amt = float(self._payload.get("amount", 0.0))
            dur = int(self._payload.get("duration", 1))
            try:
                effs = make_effect("atk_pct_buff", duration=dur, potency=amt)
                effs = _flatten_effects(effs)
                for eff in effs:
                    if isinstance(gm, EffectManager):
                        gm.apply(user, eff, source_name=f"item:{self.item_id}", ctx=ctx)
                    else:
                        eff.on_apply(user, ctx)
                evs.append(CombatEvent(text=f"{user.name} sent sa force croître (+{int(amt*100)}% ATK, {dur} tour(s)).", tag="use_buff_atk"))
            except Exception:
                evs.append(CombatEvent(text="L’élixir pétille sans effet.", tag="use_buff_atk_fail"))

        elif t == "repair_equipment":
            target = str(self._payload.get("target", "weapon")).strip().lower()
            amount = int(self._payload.get("amount", 10))
            try:
                eq = user.equipment.get(target)
            except Exception:
                eq = getattr(getattr(user, "equipment", None), target, None)
            if not eq or not hasattr(eq, "durability"):
                evs.append(CombatEvent(text="Rien à réparer.", tag="use_repair_none"))
            else:
                cur = getattr(eq.durability, "current", 0)
                mx  = getattr(eq.durability, "maximum", cur)
                new = min(mx, cur + amount)
                setattr(eq.durability, "current", new)
                evs.append(CombatEvent(text=f"{eq.name} réparée (+{new-cur}).", tag="use_repair", data={"restored": new-cur}))

        elif t == "smoke_escape":
            p = float(self._payload.get("chance", 0.5))
            roll = (rng.random() if rng else random.random())
            if roll < p:
                evs.append(CombatEvent(text="Vous profitez de la fumée pour vous éclipser !", tag="use_escape", data={"success": True}))
                evs[-1].end_combat = True
            else:
                evs.append(CombatEvent(text="La fumée se dissipe trop vite...", tag="use_escape", data={"success": False}))

        elif t == "apply_effect":
            eid = self._payload.get("effect_id")
            dur = int(self._payload.get("duration", 0))
            pot = int(self._payload.get("potency", 0))
            try:
                effs = _flatten_effects(make_effect(eid, duration=dur, potency=pot))
                for eff in effs:
                    if isinstance(gm, EffectManager):
                        gm.apply(user, eff, source_name=f"item:{self.item_id}", ctx=ctx)
                    else:
                        eff.on_apply(user, ctx)
                if effs:
                    evs.append(CombatEvent(text=f"{user.name} bénéficie de {effs[0].name}.", tag="use_apply_effect"))
                else:
                    evs.append(CombatEvent(text="Rien ne se produit.", tag="use_apply_effect_none"))
            except Exception:
                evs.append(CombatEvent(text="L’objet crépite… sans effet notable.", tag="use_unknown"))

        else:
            evs.append(CombatEvent(text="L’objet ne semble rien faire.", tag="use_none"))
            return super().on_use(user, ctx)

        return evs


def load_items() -> dict[str, Callable[[], DataConsumable]]:
    """Charge items.json et retourne un factory dict {item_id: callable()->Consumable}."""
    raw = _read_json_first("items.json")
    res: dict[str, Any] = {}
    rows: list[dict] = []

    if isinstance(raw, dict):
        for iid, row in raw.items():
            r = dict(row); r["item_id"] = iid
            rows.append(r)
    elif isinstance(raw, list):
        rows = raw
    else:
        return res

    for row in rows:
        try:
            item_id = row["item_id"]
            name = row.get("name", item_id)
            desc = row.get("description", "")
            stackable = row.get("stackable", True)
            max_stack = int(row.get("max_stack", 99))
            if isinstance(stackable, int):
                max_stack = int(stackable)
                stackable = True

            use_payload = dict(row.get("use", {}))

            tier = int(row.get("tier", row.get("tiers", 1)))
            tags = list(row.get("tags", row.get("tag", [])) or [])
            zones = [str(z).upper() for z in (row.get("zones", []) or [])]
            shop_w = int(row.get("shop_weight", 1))
            drop_w = int(row.get("drop_weight", 1))
            base_price = int(row.get("base_price", 0))

            if not stackable:
                continue

            def _factory(_id=item_id, _n=name, _d=desc, _m=max_stack, _p=use_payload,
                         _tier=tier, _tags=tags, _zones=zones, _sw=shop_w, _dw=drop_w, _bp=base_price):
                it = DataConsumable(item_id=_id, name=_n, description=_d, max_stack=_m, payload=_p, kind=None)
                setattr(it, "tier", _tier)
                setattr(it, "tags", _tags)
                setattr(it, "zones", _zones)
                setattr(it, "shop_weight", _sw)
                setattr(it, "drop_weight", _dw)
                setattr(it, "base_price", _bp)
                setattr(it, "stackable", True)
                return it

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
    behavior: str | None = None
    drops: dict | None = None

    def build(self, *, level: int) -> Enemy:
        # applique un scaling simple
        atk = self.base_stats.attack + int(self.scaling.get("attack_per_level", 0) * max(0, level - 1))
        df  = self.base_stats.defense + int(self.scaling.get("defense_per_level", 0) * max(0, level - 1))
        lk  = self.base_stats.luck
        hp  = self.hp_max + int(self.scaling.get("hp_per_level", 0) * max(0, level - 1))

        e = Enemy(
            name=self.name,
            base_stats=Stats(attack=atk, defense=df, luck=lk),
            base_hp_max=hp,
            base_sp_max=self.sp_max
        )
        try:
            key = (self.behavior or "balanced").strip().lower()
            cls = BEHAVIOR_REGISTRY.get(key)
            e.behavior_ai = cls() if cls else None
        except Exception:
            e.behavior_ai = None
        setattr(e, "attacks", list(self.attacks))
        setattr(e, "attack_weights", list(self.attack_weights or [1] * max(1, len(self.attacks))))
        setattr(e, "enemy_id", self.enemy_id)
        return e


def load_enemy_blueprints(attacks_registry: dict[str, Attack]) -> dict[str, EnemyBlueprint]:
    """Lit data/enemies/*.json ; chaque .json peut être un dict (1 ennemi) ou une liste d’ennemis."""
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
                    atk_objs = []
                    # 1) via ids du registre
                    for k in atk_keys:
                        kk = str(k).strip().lower()
                        if kk in attacks_registry:
                            atk_objs.append(attacks_registry[kk]); continue
                        # 2) fallback content.actions
                        try:
                            import content.actions as _atcs
                            cand = getattr(_atcs, k, None)
                            if isinstance(cand, Attack):
                                atk_objs.append(cand); continue
                        except Exception:
                            pass
                        # 3) match sur Attack.name
                        try:
                            import content.actions as _atcs
                            for _v in vars(_atcs).values():
                                if isinstance(_v, Attack) and str(_v.name).strip().lower() == kk:
                                    atk_objs.append(_v); break
                        except Exception:
                            pass
                    weights = list(row.get("attack_weights", [])) or [1] * max(1, len(atk_objs))
                    scaling = dict(row.get("scaling", {}))
                    behavior = row.get("behavior", None)
                    drops = row.get("drops", None)
                    drops = dict(drops) if isinstance(drops, dict) else None
                    res[eid] = EnemyBlueprint(
                        enemy_id=eid, name=name, base_stats=base_stats, hp_max=hp, sp_max=sp,
                        attacks=atk_objs, attack_weights=weights, scaling=scaling,
                        gold_max=gold_max, gold_min=gold_min, behavior=behavior, drops=drops
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
    out = {"weapon": {}, "armor": {}, "artifact": {}}
    for base in default_data_dirs():
        eqdir = Path(base) / "equipment"
        if not eqdir.is_dir():
            continue
        for fname, kind in (("weapons.json","weapon"),("armors.json","armor"),("artifacts.json","artifact")):
            p = eqdir / fname
            if not p.exists(): 
                continue
            try:
                rows = json.loads(p.read_text(encoding="utf-8"))
                for r in rows:
                    zones = [str(z).upper() for z in r.get("zones", [])]
                    out[kind][r["id"]] = zones
            except Exception:
                pass
    return out


def load_equipment_banks() -> tuple[list[Weapon], list[Armor], list[Artifact]]:
    """Lit src/data/equipment/*.json et retourne 3 LISTES de prototypes (instances) avec méta + clone()."""
    w_protos: list[Weapon] = []
    a_protos: list[Armor] = []
    r_protos: list[Artifact] = []

    def _attach_meta(inst, row: dict):
        # métadonnées optionnelles utilisées par shop/drops/filtrage
        setattr(inst, "tier", int(row.get("tier", row.get("tiers", 1))))
        setattr(inst, "tags", list(row.get("tags", row.get("tag", [])) or []))
        setattr(inst, "zones", [str(z).upper() for z in (row.get("zones", []) or [])])
        setattr(inst, "base_price", int(row.get("base_price", 50)))
        # méthode clone (ferme sur les args du constructeur)
        if not hasattr(inst, "clone"):
            ctor = type(inst)
            if isinstance(inst, Weapon):
                args = dict(name=inst.name, durability_max=inst.durability.maximum,
                            bonus_attack=inst.bonus_attack, description=getattr(inst, "description", ""))
            elif isinstance(inst, Armor):
                args = dict(name=inst.name, durability_max=inst.durability.maximum,
                            bonus_defense=inst.bonus_defense, description=getattr(inst, "description", ""))
            elif isinstance(inst, Artifact):
                args = dict(name=inst.name, durability_max=inst.durability.maximum,
                            atk_pct=inst.atk_pct, def_pct=inst.def_pct, lck_pct=getattr(inst, "lck_pct", 0.0),
                            description=getattr(inst, "description", ""))
            def _clone(_ctor=ctor, _args=args):
                return _ctor(**_args)
            setattr(inst, "clone", _clone)
        return inst

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
                    name = row.get("name", row.get("id", "weapon"))
                    dmax = int(row.get("durability_max", 10))
                    batk = int(row.get("bonus_attack", 0))
                    desc = row.get("description", "")
                    inst = Weapon(name=name, durability_max=dmax, bonus_attack=batk, description=desc)
                    w_protos.append(_attach_meta(inst, row))
            except Exception:
                pass

        # armors
        apath = eqdir / "armors.json"
        if apath.exists():
            try:
                rows = json.loads(apath.read_text(encoding="utf-8"))
                for row in rows:
                    name = row.get("name", row.get("id", "armor"))
                    dmax = int(row.get("durability_max", 12))
                    bdef = int(row.get("bonus_defense", 0))
                    desc = row.get("description", "")
                    inst = Armor(name=name, durability_max=dmax, bonus_defense=bdef, description=desc)
                    a_protos.append(_attach_meta(inst, row))
            except Exception:
                pass

        # artifacts
        rpath = eqdir / "artifacts.json"
        if rpath.exists():
            try:
                rows = json.loads(rpath.read_text(encoding="utf-8"))
                for row in rows:
                    name = row.get("name", row.get("id", "artifact"))
                    dmax = int(row.get("durability_max", 8))
                    ap = float(row.get("atk_pct", 0.0))
                    dp = float(row.get("def_pct", 0.0))
                    lp = float(row.get("lck_pct", 0.0))
                    desc = row.get("description", "")
                    inst = Artifact(name=name, durability_max=dmax, atk_pct=ap, def_pct=dp, lck_pct=lp, description=desc)
                    r_protos.append(_attach_meta(inst, row))
            except Exception:
                pass

    return w_protos, a_protos, r_protos
