from __future__ import annotations
"""Sauvegarde/Chargement JSON — minimal, versionné, sans dépendance UI.

Ce module convertit l'état de la partie en dict JSON, et réciproquement.
Il n'importe pas l'UI. Il s'appuie sur les registres/factories existants.

Contenu sauvegardé:
- version
- rng_state (optionnel)
- player: base_stats, hp/sp (max & current), class_key, name
- wallet: gold
- zone: type, level, explored
- inventory: [{item_id, qty}]
- equipment (slots): weapon/armor/artifact + champs spécifiques + durabilité
- loadout: dict d'Attacks pour primary/skill/utility (+ class_attack si présent)
- effects: [{effect_id, potency, remaining}] sur le joueur (si EffectManager actif)

Remarques:
- On stocke les Attacks du loadout **inline** (pas par référence), pour être indépendant
  des fichiers data à la restauration.
- Les Items sont **par id** (via ITEM_FACTORY) car ils sont standardisés.
"""

import json
from typing import TYPE_CHECKING
import inspect

# ——— Imports moteur ———
from core import effects
from core.player import Player
from core.attack import Attack
from core.resource import Resource
from core.inventory import Inventory
from core.supply import Wallet
from core.effects import Effect, PoisonEffect, AttackBuffEffect, DefenseBuffEffect, LuckBuffEffect
_EFFECT_REGISTRY = {
    name: cls
    for name, cls in inspect.getmembers(effects, inspect.isclass)
    if issubclass(cls, Effect)
}
from content.effects_bank import make_effect
from core.loadout import Loadout, LoadoutManager
from core.equipment import Weapon, Armor, Artifact, Equipment
# from game.game_loop import GameLoop

# Équipements concrets

# Factories d'items (consommables)
try:
    from content.items import ITEM_FACTORY as ITEM_FACTORY_CODE
except:
    ITEM_FACTORY_CODE = {}

if TYPE_CHECKING:
    from game.game_loop import GameLoop
    from core.effect_manager import EffectManager

SAVE_VERSION = 1


# --------------------- utilitaires ---------------------

def _attack_to_dict(atk: Attack) -> dict:
    d = {
        "name": atk.name,
        "base_damage": atk.base_damage,
        "variance": atk.variance,
        "cost": atk.cost,
        "crit_multiplier": getattr(atk, "crit_multiplier", 2.0),
        "ignore_defense_pct": getattr(atk, "ignore_defense_pct", 0.0),
        "true_damage": getattr(atk, "true_damage", 0),
    }
    # Effets (facultatif): si l'attaque porte des effets instanciés, on les réduit à effect_id/potency/duration
    if atk.effects:
        effs = []
        for e in atk.effects:
            eid = getattr(e, "effect_id", None) or getattr(e, "name", None)
            effs.append({
                "effect_id": str(eid) if eid is not None else "custom",
                "duration": int(getattr(e, "remaining", getattr(e, "duration", 0))),
                "potency": int(getattr(e, "potency", 0)),
            })
        if effs:
            d["effects"] = effs
        # Cible (si tu as ajouté ce champ): "self"/"enemy"
        if hasattr(atk, "target"):
            d["target"] = getattr(atk, "target")
    return d

def _attack_from_dict(d: dict) -> Attack:
    # Reconstitue l'attaque (effets via effects_bank)
    effs = []
    for e in d.get("effects", []) or []:
        effs.append(make_effect(e.get("effect_id"), duration=int(e.get("duration", 0)), potency=int(e.get("potency", 0))))
    return Attack(
        name=d.get("name", "Attaque"),
        base_damage=int(d.get("base_damage", 0)),
        variance=int(d.get("variance", 0)),
        cost=int(d.get("cost", 0)),
        crit_multiplier=float(d.get("crit_multiplier", 2.0)),
        ignore_defense_pct=float(d.get("ignore_defense_pct", 0.0)),
        true_damage=int(d.get("true_damage", 0)),
        effects=effs,
        **({"target": d["target"]} if "target" in d else {})
    )


def _equipment_slot_to_dict(slot_obj: Equipment) -> dict | None:
    if slot_obj is None:
        return None
    base = {
        "name": getattr(slot_obj, "name", "???"),
        "durability": {
            "current": slot_obj.durability.current,
            "maximum": slot_obj.durability.maximum,
        }
    }
    if isinstance(slot_obj, Weapon):
        base.update({
            "kind": slot_obj._slot,
            "bonus_attack": int(getattr(slot_obj, "bonus_attack", 0)),
        })
    elif isinstance(slot_obj, Armor):
        base.update({"kind": slot_obj._slot, "bonus_defense": getattr(slot_obj, "bonus_defense", 0)})
    elif isinstance(slot_obj, Artifact):
        spm = slot_obj.stat_percent_mod()
        base.update({"kind": slot_obj._slot, "atk_pct": spm.attack_pct, "def_pct": spm.defense_pct, "lck_pct": spm.luck_pct})
    else:
        base.update({"kind": "unknown"})
    return base

def _equipment_slot_from_dict(d: dict | None):
    if not d:
        return None
    k = d.get("kind")
    name = d.get("name", "???")
    dur = d.get("durability", {"current": 1, "maximum": 1})
    if k == "weapon":
        bonus = int(d.get("bonus_attack", 0))
        obj = Weapon(
            name=name, 
            durability_max=int(dur.get("maximum", 1)), 
            bonus_attack=bonus
            )
    elif k == "armor":
        obj = Armor(
            name=name, 
            durability_max=int(dur.get("maximum", 1)), 
            bonus_defense=int(d.get("bonus_defense", 0))
            )
    elif k == "artifact":
        obj = Artifact(
            name=name, 
            durability_max=int(dur.get("maximum", 1)),
            atk_pct=float(d.get("atk_pct", 0.0)), 
            def_pct=float(d.get("def_pct", 0.0)),
            lck_pct=float(d.get("lck_pct", 0.0))
            )
    else:
        return None
    # positionner la durabilité courante
    obj.durability.current = int(dur.get("current", obj.durability.maximum))
    return obj


# --------------------- API publique ---------------------

def game_to_dict0(loop: GameLoop) -> dict:
    """Capture l'état du GameLoop (sans UI) en dict JSON-sérialisable."""
    player: Player = loop.player
    inv: Inventory = loop.player_inventory
    wallet: Wallet = loop.wallet
    effects_mgr: EffectManager = loop.effects

    # Player de base
    pdata = {
        "name": player.name,
        "class_key": player.player_class_key,
        "base_stats": {"attack": player.base_stats.attack, "defense": player.base_stats.defense, "luck": player.base_stats.luck},
        "hp": {"current": player.hp, "maximum": player.max_hp},
        "sp": {"current": player.sp, "maximum": player.max_sp},
    }

    # Zone/progression minimale
    z = loop.zone
    zdata = {
        "type": z.zone_type.name if z.zone_type else None,
        "level": getattr(z, "level", 1),
        "explored": getattr(z, "explored", 0),
        "boss_ready": getattr(z, "boss_ready", False),
    }

    # Équipements (slots)
    eq = getattr(loop.player, "equipment", None)
    equip = {
        "weapon": _equipment_slot_to_dict(getattr(eq, "weapon", None)),
        "armor": _equipment_slot_to_dict(getattr(eq, "armor", None)),
        "artifact": _equipment_slot_to_dict(getattr(eq, "artifact", None)),
    }

    # Inventaire (items stackables)
    inv_rows = []
    try:
        for row in inv.list_summary():
            if row["kind"] == "item":
                inv_rows.append({"item_id": row["id"], "qty": int(row["qty"])})
    except Exception:
        # Fallback minimaliste si list_summary() n'est pas dispo
        stacks = getattr(inv, "_stacks", {}) or {}
        for item_id, lst in stacks.items():
            total = sum(int(getattr(s, "qty", 0)) for s in lst)
            if total > 0:
                inv_rows.append({"item_id": str(item_id), "qty": total})

    # Loadout courant (3 attaques + attaque de classe si existante)
    lo_mgr = loop.loadouts
    lo = lo_mgr.get(player) if lo_mgr else None
    ld = {}
    if lo:
        ld = {
            "primary": _attack_to_dict(lo.primary),
            "skill": _attack_to_dict(lo.skill),
            "utility": _attack_to_dict(lo.utility),
        }
    class_atk = getattr(player, "class_attack", None)
    if class_atk is not None:
        ld["class_attack"] = _attack_to_dict(class_atk)

    # Effets actifs sur le joueur
    effs = effects_mgr.snapshot(player) if effects_mgr else []

    # RNG — optionnel: on ne sérialise pas l'état Python interne par défaut
    rng_state = None
    try:
        st = loop.rng.getstate()
        # transformer tuple imbriqué en listes pour JSON
        def _to_jsonable(x):
            if isinstance(x, tuple):
                return [_to_jsonable(y) for y in x]
            if isinstance(x, (list, int, str)):
                return x
            return str(x)
        rng_state = _to_jsonable(st)
    except Exception:
        rng_state = None

    return {
        "version": SAVE_VERSION,
        "player": pdata,
        "wallet": {"gold": wallet.gold},
        "zone": zdata,
        "inventory": inv_rows,
        "equipment": equip,
        "loadout": ld,
        "effects": effs,
        "rng_state": rng_state,
    }

def game_to_dict(game: GameLoop) -> dict:
    """Snapshot sérialisable de l'état *essentiel* de la partie (pour JSON).
    Ne dépend pas de l'UI. Se contente de types simples (int/float/str/dict/list).
    """
    # Imports locaux pour éviter les cycles au chargement du module
    from core.equipment import Weapon, Armor, Artifact

    def _res_to_dict(res) -> dict:
        return {"current": int(getattr(res, "current", 0)),
                "maximum": int(getattr(res, "maximum", 0))}

    def _stats_to_dict(stats) -> dict:
        return {
            "attack": int(getattr(stats, "attack", 0)),
            "defense": int(getattr(stats, "defense", 0)),
            "luck": int(getattr(stats, "luck", 0)),
            "crit_multiplier": float(getattr(stats, "crit_multiplier", 2.0)),
        }

    def _equip_slot_to_dict(obj) -> dict | None:
        if obj is None:
            return None
        base = {
            "name": getattr(obj, "name", ""),
            "description": getattr(obj, "description", ""),
            "durability": {
                "current": int(getattr(getattr(obj, "durability", None), "current", 0)),
                "maximum": int(getattr(getattr(obj, "durability", None), "maximum", 0)),
            },
        }
        # Type concret & champs spécifiques
        if isinstance(obj, Weapon):
            base.update({"kind": "weapon", "bonus_attack": int(getattr(obj, "bonus_attack", 0))})
        elif isinstance(obj, Armor):
            base.update({"kind": "armor", "bonus_defense": int(getattr(obj, "bonus_defense", 0))})
        elif isinstance(obj, Artifact):
            base.update({
                "kind": "artifact",
                "atk_pct": float(getattr(obj, "atk_pct", 0.0)),
                "def_pct": float(getattr(obj, "def_pct", 0.0)),
                "lck_pct": float(getattr(obj, "lck_pct", 0.0)),
            })
        else:
            base.update({"kind": "unknown"})
        return base

    def _inventory_to_dict(inv) -> dict:
        # Items stackables (total par item_id)
        items_rows = []
        stacks = getattr(inv, "_stacks", {}) or {}
        for item_id, lst in stacks.items():
            total = sum(int(getattr(st, "qty", 0)) for st in lst)
            if total > 0:
                items_rows.append({"item_id": str(item_id), "qty": int(total)})
        # Équipements non stackables
        equips_rows = []
        for eq in list(getattr(inv, "_equipment", []) or []):
            equips_rows.append(_equip_slot_to_dict(eq))
        return {"items": items_rows, "equipment": equips_rows, "capacity": int(getattr(inv, "capacity", 0))}

    # ---- Player & Game ----
    p = game.player

    # Loadout → on capture juste les noms (résolution à la lecture)
    loadout_row = {"primary": None, "skill": None, "utility": None, "class_attack_unlocked": False}
    try:
        ld = game.loadouts.get(p)
        if ld:
            for slot in ("primary", "skill", "utility"):
                atk = getattr(ld, slot, None)
                loadout_row[slot] = getattr(atk, "name", None) if atk else None
    except Exception:
        pass
    loadout_row["class_attack_unlocked"] = bool(getattr(p, "class_attack_unlocked", False))

    out = {
        "version": int(globals().get("SAVE_VERSION", 1)),
        "player": {
            "name": getattr(p, "name", "Héros"),
            "class_key": getattr(p, "player_class_key", "guerrier"),
            "base_stats": _stats_to_dict(getattr(p, "base_stats", None)),
            "hp": _res_to_dict(getattr(p, "hp_res", None)),
            "sp": _res_to_dict(getattr(p, "sp_res", None)),
        },
        "wallet": {"gold": int(getattr(getattr(game, "wallet", None), "gold", 0))},
        "zone": {
            "type": getattr(getattr(getattr(game, "zone", None), "zone_type", None), "name", "RUINS"),
            "level": int(getattr(getattr(game, "zone", None), "level", 1)),
            "explored": int(getattr(getattr(game, "zone", None), "explored", 0)),
        },
        "equipment": {
            "weapon": _equip_slot_to_dict(getattr(getattr(p, "equipment", None), "weapon", None)),
            "armor": _equip_slot_to_dict(getattr(getattr(p, "equipment", None), "armor", None)),
            "artifact": _equip_slot_to_dict(getattr(getattr(p, "equipment", None), "artifact", None)),
        },
        "inventory": _inventory_to_dict(getattr(game, "player_inventory", None)),
        "effects": [],
        "loadout": loadout_row,
        "rng_seed": getattr(game, "seed", None),
    }
    try:
        # EffectManager.snapshot retourne déjà une liste de dict
        out["effects"] = game.effects.snapshot(p)
    except Exception:
        out["effects"] = []
    return out


def dict_to_game0(data: dict, *, io=None):
    """Reconstruit un GameLoop neuf à partir d'un dict de save.
    Nécessite les modules du jeu (Player, GameLoop, etc.) mais pas l'UI spécifique.
    """
    # Imports tardifs pour éviter les cycles
    from game.game_loop import GameLoop, ZoneType
    from core.stats import Stats

    ver = int(data.get("version", 0))
    if ver != SAVE_VERSION:
        # politique simple: on tente quand même
        pass

    p = data["player"]
    name = p["name"]
    class_key = (p["class_key"] or "").lower()
    base_stats = Stats(attack=p["base_stats"]["attack"], defense=p["base_stats"]["defense"], luck=p["base_stats"]["luck"])
    base_hp_max = int(p["hp"]["maximum"])
    base_sp_max = int(p["sp"]["maximum"])

    # Player neuf
    player = Player(name=name, player_class_key=class_key, base_stats=base_stats, base_hp_max=base_hp_max, base_sp_max=base_sp_max)
    # Rétablir les valeurs courantes hp/sp
    # (on suppose que Entity expose hp/sp en propriété directe)
    player.hp_res.current = int(p["hp"]["current"])
    player.sp_res.current = int(p["sp"]["current"])

    # Boucle et systèmes
    loop = GameLoop(player=player, io=io, seed=None)

    # Wallet
    loop.wallet = Wallet(int(data.get("wallet", {}).get("gold", 0)))

    # Zone
    z = data.get("zone", {})
    # On suppose que loop.zone existe déjà; on écrase ses champs si présents
    if getattr(loop, "zone", None):
        try:
            if z.get("type"):
                loop.zone.zone_type = ZoneType[z["type"]]
        except Exception:
            pass
        loop.zone.level = int(z.get("level", loop.zone.level))
        loop.zone.explored = int(z.get("explored", getattr(loop.zone, "explored", 0)))

    # Équipements (équipe via Player.equip pour activer les bonus)
    eq = data.get("equipment", {})
    for slot in ("weapon", "armor", "artifact"):
        obj = _equipment_slot_from_dict(eq.get(slot))
        if obj:
            loop.player.equip(obj, slot)

    # Inventaire (stackables)
    inv_rows = data.get("inventory", [])
    for row in inv_rows:
        factory = ITEM_FACTORY_CODE.get(row["item_id"])
        if not factory:
            continue
        item = factory()
        loop.player_inventory.add_item(item, qty=int(row["qty"]))

    # Loadout
    lo = data.get("loadout", {})
    if lo:
        loop.loadouts = getattr(loop, "loadouts", LoadoutManager())
        primary = _attack_from_dict(lo["primary"]) if "primary" in lo else None
        skill   = _attack_from_dict(lo["skill"]) if "skill" in lo else None
        utility = _attack_from_dict(lo["utility"]) if "utility" in lo else None
        if primary and skill and utility:
            loop.loadouts.set(loop.player, Loadout(primary=primary, skill=skill, utility=utility))
        if "class_attack" in lo:
            setattr(loop.player, "class_attack", _attack_from_dict(lo["class_attack"]))

    # Effets actifs (si EffectManager présent)
    if getattr(loop, "effects", None):
        loop.effects.restore(loop.player, data.get("effects", []), registry=_EFFECT_REGISTRY, ctx=None)

    # RNG (facultatif)
    try:
        if data.get("rng_state"):
            def _to_tuple(x):
                if isinstance(x, list):
                    return tuple(_to_tuple(y) for y in x)
                return x
            loop.rng.setstate(_to_tuple(data["rng_state"]))
    except Exception:
        pass

    return loop

def dict_to_game(data: dict, *, io=None):
    """Reconstruit un GameLoop complet depuis un dict JSON.
    Tolérant aux versions et clés manquantes.
    """
    # Imports locaux pour éviter les cycles
    from core.stats import Stats
    from core.player import Player
    from core.resource import Resource
    from core.equipment import Weapon, Armor, Artifact
    from core.equipment_set import EquipmentSet
    from core.loadout import Loadout
    from game.game_loop import GameLoop, ZoneType
    import inspect
    from core import effects as _effects_mod
    from core.effects import Effect as _BaseEffect

    def _zone_from_name(name: str | None):
        if not name:
            return None
        try:
            return ZoneType[name]
        except Exception:
            return None

    def _res_apply(entity, res_name: str, row: dict):
        # Fixe maximum puis current (sans préserver le ratio)
        res: Resource = getattr(entity, f"{res_name}_res")
        if isinstance(row, dict):
            mx = int(row.get("maximum", getattr(res, "maximum", 0)))
            cur = int(row.get("current", getattr(res, "current", 0)))
            res.set_maximum(mx, preserve_ratio=False)
            res.current = max(0, min(cur, res.maximum))

    def _stats_from_dict(d: dict) -> Stats:
        d = d or {}
        return Stats(
            int(d.get("attack", 0)),
            int(d.get("defense", 0)),
            int(d.get("luck", 0)),
            float(d.get("crit_multiplier", 2.0)),
        )

    def _equip_from_row(row) -> object | None:
        if not row or not isinstance(row, dict):
            return None
        k = row.get("kind")
        name = row.get("name", "")
        desc = row.get("description", "")
        dur = row.get("durability", {}) or {}
        dmax = int(dur.get("maximum", 1))
        cur = int(dur.get("current", dmax))
        if k == "weapon":
            obj = Weapon(name=name, durability_max=dmax, bonus_attack=int(row.get("bonus_attack", 0)), description=desc)
        elif k == "armor":
            obj = Armor(name=name, durability_max=dmax, bonus_defense=int(row.get("bonus_defense", 0)), description=desc)
        elif k == "artifact":
            obj = Artifact(name=name, durability_max=dmax,
                           atk_pct=float(row.get("atk_pct", 0.0)),
                           def_pct=float(row.get("def_pct", 0.0)),
                           lck_pct=float(row.get("lck_pct", 0.0)),
                           description=desc)
        else:
            return None
        # appliquer current sans déclencher de ratio
        try:
            obj.durability.set_maximum(dmax, preserve_ratio=False)
            obj.durability.current = max(0, min(cur, obj.durability.maximum))
        except Exception:
            pass
        return obj

    # ---------- Player ----------
    p_row = data.get("player", {}) or {}
    name = p_row.get("name", "Hero")
    class_key = (p_row.get("class_key") or "guerrier").strip().lower()
    base_stats = _stats_from_dict(p_row.get("base_stats"))
    hp_row = p_row.get("hp", {})
    sp_row = p_row.get("sp", {})

    # Player.__init__ applique déjà la classe → on fournit des bases, puis on écrase
    base_hp_max = int(hp_row.get("maximum", 30) or 30)
    base_sp_max = int(sp_row.get("maximum", 10) or 10)
    player = Player(name=name, player_class_key=class_key, base_stats=base_stats,
                    base_hp_max=base_hp_max, base_sp_max=base_sp_max)

    # Fixer HP/SP aux valeurs sauvegardées (après application classe)
    _res_apply(player, "hp", hp_row)
    _res_apply(player, "sp", sp_row)

    # ---------- GameLoop ----------
    zrow = data.get("zone", {}) or {}
    seed = data.get("rng_seed")
    loop = GameLoop(player=player, io=io, seed=seed,
                    initial_zone=_zone_from_name(zrow.get("type")),
                    start_level=int(zrow.get("level", 1)))
    try:
        loop.zone.explored = int(zrow.get("explored", 0))
    except Exception:
        pass

    # ---------- Wallet ----------
    try:
        loop.wallet.gold = int(data.get("wallet", {}).get("gold", 0))
    except Exception:
        pass

    # ---------- Equipment slots ----------
    eqpack = data.get("equipment", {}) or {}
    for slot in ("weapon", "armor", "artifact"):
        obj = _equip_from_row(eqpack.get(slot))
        if obj is not None:
            try:
                player.equip(obj, slot)  # applique bonus via Player.equip
            except Exception:
                # fallback: remplacement brut
                try:
                    player.equipment.replace(slot=slot, item=obj)
                except Exception:
                    pass

    # ---------- Inventory ----------
    # Items stackables (via ITEM_FACTORY si dispo)
    try:
        inv_row = data.get("inventory", {}) or {}
        from content.items import ITEM_FACTORY as _IF  # id -> prototype Item/Consumable
    except Exception:
        _IF = {}

    try:
        inv = loop.player_inventory
        for r in inv_row.get("items", []) or []:
            iid = str(r.get("item_id", "")).strip().lower()
            qty = int(r.get("qty", 0))
            proto = _IF.get(iid)
            if proto and qty > 0:
                inv.add_item(proto, qty)
    except Exception:
        pass

    # Équipements dans l’inventaire
    try:
        inv = loop.player_inventory
        for r in inv_row.get("equipment", []) or []:
            obj = _equip_from_row(r)
            if obj is not None:
                inv.add_equipment(obj)
        # capacité si présente
        cap = int(inv_row.get("capacity", 0))
        if cap > 0:
            inv.capacity = cap
    except Exception:
        pass

    # ---------- Effects ----------
    # Registre auto à partir de core.effects (cls_name -> classe)
    try:
        _EFFECT_REGISTRY = {
            name: cls
            for name, cls in inspect.getmembers(_effects_mod, inspect.isclass)
            if issubclass(cls, _BaseEffect)
        }
        loop.effects.restore(loop.player, data.get("effects", []) or [], registry=_EFFECT_REGISTRY, ctx=None)
    except Exception:
        pass

    # ---------- Loadout ----------
    try:
        lrow = data.get("loadout", {}) or {}
        wanted = {k: (v or "").strip() or None for k, v in lrow.items() if k in ("primary", "skill", "utility")}
        # Registry d'attaques (id -> Attack)
        from core.data_loader import load_attacks
        attacks_reg = load_attacks()  # {attack_id: Attack}
        # Build reverse map nom (lower) -> Attack
        name_map = {}
        for atk in attacks_reg.values():
            nm = (getattr(atk, "name", "") or "").strip().lower()
            if nm and nm not in name_map:
                name_map[nm] = atk
        # Résolution par nom
        def _resolve(n):
            return name_map.get((n or "").strip().lower())

        loadout = Loadout(
            primary=_resolve(wanted.get("primary")),
            skill=_resolve(wanted.get("skill")),
            utility=_resolve(wanted.get("utility")),
        )
        loop.loadouts.set(loop.player, loadout)
        # Flag classe
        setattr(loop.player, "class_attack_unlocked", bool(lrow.get("class_attack_unlocked", False)))
    except Exception:
        pass

    return loop

# --------------------- helpers fichiers ---------------------

def save_to_file(loop, path: str) -> bool:
    try:
        payload = game_to_dict(loop)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_from_file(path: str, *, io=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return dict_to_game(data, io=io)
    except Exception:
        return None

# ------- SELFTEST (à coller tout en bas de src/core/save.py) -------

def _build_min_game():
    """Construit une partie minimale pour tester save/load."""
    from core.stats import Stats
    from core.player import Player
    from game.game_loop import GameLoop

    p = Player(
        name="Testeur",
        player_class_key="guerrier",   # adapte si besoin
        base_stats=Stats(8, 4, 2, 2.0),
        base_hp_max=30,
        base_sp_max=10,
    )
    # Zone/seed simples ; GameLoop se charge d'initialiser le reste
    g = GameLoop(player=p, io=None, seed=42, initial_zone=None, start_level=2)
    return g

def _selftest_roundtrip(slot_path: str = "save_slot_selftest.json") -> None:
    """Sauvegarde -> chargement -> quelques asserts basiques."""
    g1 = _build_min_game()

    ok = save_to_file(g1, slot_path)
    assert ok, "save_to_file a échoué"

    g2 = load_from_file(slot_path, io=None)
    assert g2 is not None, "load_from_file a échoué"

    # Vérifications minimales (tu peux en ajouter d'autres)
    assert g2.player.name == g1.player.name, "Nom du joueur différent après rechargement"
    assert g2.zone.level == g1.zone.level, "Level de zone différent"
    assert g2.wallet.gold == g1.wallet.gold, "Gold du wallet différent"

    print("ROUNDTRIP OK →", slot_path)

if __name__ == "__main__":
    _selftest_roundtrip()
