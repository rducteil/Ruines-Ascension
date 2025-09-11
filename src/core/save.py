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

# ——— Imports moteur ———
from core.stats import Stats
from core.player import Player
from core.attack import Attack
from core.resource import Resource
from core.player_class import CLASSES as CLASS_REG
from core.inventory import Inventory
from core.supply import Wallet
from core.effects import Effect
from content.effects_bank import make_effect
from core.loadout import Loadout, LoadoutManager
# from game.game_loop import GameLoop

# Équipements concrets
from core.equipment import Weapon, Armor, Artifact

# Factories d'items (consommables)
from content.items import ITEM_FACTORY as ITEM_FACTORY_CODE

if TYPE_CHECKING:
    from game.game_loop import GameLoop

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


def _equipment_slot_to_dict(slot_obj) -> dict | None:
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
        base.update({"kind": "weapon", "bonus_attack": slot_obj.bonus_attack})
    elif isinstance(slot_obj, Armor):
        base.update({"kind": "armor", "bonus_defense": slot_obj.bonus_defense})
    elif isinstance(slot_obj, Artifact):
        # artefacts: % ATK/DEF
        spm = slot_obj.stat_percent_mod()
        base.update({"kind": "artifact", "atk_pct": spm.attack_pct, "def_pct": spm.defense_pct})
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
        obj = Weapon(name=name, durability_max=int(dur.get("maximum", 1)), bonus_attack=int(d.get("bonus_attack", 0)))
    elif k == "armor":
        obj = Armor(name=name, durability_max=int(dur.get("maximum", 1)), bonus_defense=int(d.get("bonus_defense", 0)))
    elif k == "artifact":
        obj = Artifact(name=name, durability_max=int(dur.get("maximum", 1)),
                       atk_pct=float(d.get("atk_pct", 0.0)), def_pct=float(d.get("def_pct", 0.0)))
    else:
        return None
    # positionner la durabilité courante
    obj.durability.current = int(dur.get("current", obj.durability.maximum))
    return obj


def _effects_to_list(effects_mgr, target) -> list[dict]:
    """Réduit les effets actifs sur `target` (s'ils existent) à des payloads JSON."""
    out: list[dict] = []
    if effects_mgr is None:
        return out
    # On suppose que le manager expose something comme get_active(target) -> Iterable[Effect]
    try:
        active = list(effects_mgr.get_active(target))
    except Exception:
        active = []
    for e in active:
        eid = getattr(e, "effect_id", None) or getattr(e, "name", None)
        out.append({
            "effect_id": str(eid) if eid is not None else "custom",
            "duration": int(getattr(e, "remaining", getattr(e, "duration", 0))),
            "potency": int(getattr(e, "potency", 0)),
        })
    return out


def _effects_from_list(effects_mgr, target, payloads: list[dict], ctx=None) -> None:
    if effects_mgr is None:
        return
    for p in payloads or []:
        eff = make_effect(p.get("effect_id"), duration=int(p.get("duration", 0)), potency=int(p.get("potency", 0)))
        try:
            effects_mgr.apply(target, eff, source_name="save:load", ctx=ctx)
        except Exception:
            # fallback: appliquer sans manager
            eff.on_apply(target, ctx)


# --------------------- API publique ---------------------

def game_to_dict(loop: GameLoop) -> dict:
    """Capture l'état du GameLoop (sans UI) en dict JSON-sérialisable."""
    player: Player = loop.player
    inv: Inventory = loop.player_inventory
    wallet: Wallet = loop.wallet
    effects_mgr = getattr(loop, "effects", None)

    # Player de base
    pdata = {
        "name": player.name,
        "class_key": getattr(player, "player_class_key", None),
        "base_stats": {"attack": player.base_stats.attack, "defense": player.base_stats.defense, "luck": player.base_stats.luck},
        "hp": {"current": player.hp, "maximum": player.max_hp},
        "sp": {"current": player.sp, "maximum": player.max_sp},
    }

    # Zone/progression minimale
    z = getattr(loop, "zone", None)
    zdata = {
        "type": getattr(z, "zone_type", None).name if getattr(z, "zone_type", None) else None,
        "level": getattr(z, "level", 1),
        "explored": getattr(z, "explored", 0),
        "boss_ready": getattr(z, "boss_ready", False),
    }

    # Équipements (slots)
    equip = {
        "weapon": _equipment_slot_to_dict(getattr(player, "weapon", None)),
        "armor": _equipment_slot_to_dict(getattr(player, "armor", None)),
        "artifact": _equipment_slot_to_dict(getattr(player, "artifact", None)),
    }

    # Inventaire (items stackables)
    inv_rows = []
    for row in inv.list_summary():
        if row["kind"] == "item":
            inv_rows.append({"item_id": row["id"], "qty": int(row["qty"])})

    # Loadout courant (3 attaques + attaque de classe si existante)
    lo_mgr = getattr(loop, "loadouts", None)
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


def dict_to_game(data: dict, *, io=None):
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
        loop.effects.restore(loop.player, data.get("effects", []), registry={}, ctx=None)

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
