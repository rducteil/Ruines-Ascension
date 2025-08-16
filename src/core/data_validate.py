from __future__ import annotations
"""Validation des fichiers data (enemies, encounters, equipment, events).
Exécution:
    python -m core.data_validate
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from core.data_loader import (
    load_attacks,
    load_enemy_blueprints,
    load_encounter_tables,
    load_equipment_banks,
)
from core.data_paths import default_data_dirs

# --- Constantes de zones (strings, car les JSON stockent des noms) ---
ZONE_NAMES = {"RUINS", "CAVES", "FOREST", "DESERT", "SWAMP"}

# --- Effets d'event pris en charge (cf. EventEngine._apply_effect_payload) ---
EVENT_EFFECT_TYPES = {"heal_hp_pct", "give_gold", "damage_hp", "apply_effect", "start_combat"}

# --- Stats autorisées dans "requires" ---
REQUIRE_STATS = {"attack", "defense", "luck"}


@dataclass
class Report:
    errors: List[str]
    warnings: List[str]

    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "Report") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def print(self) -> None:
        print("=== Data validation report ===")
        if self.errors:
            print(f"[ERROR] {len(self.errors)} problem(s):")
            for e in self.errors:
                print("  -", e)
        else:
            print("No errors.")
        if self.warnings:
            print(f"[WARN]  {len(self.warnings)} warning(s):")
            for w in self.warnings:
                print("  -", w)


# ---------- Helpers ----------

def _pos_int(value: Any, name: str, ctx: str, *, zero_ok: bool = False) -> List[str]:
    errs: List[str] = []
    try:
        iv = int(value)
        if (iv < 0) or (iv == 0 and not zero_ok):
            errs.append(f"{ctx}: '{name}' must be > 0 (got {iv})")
    except Exception:
        errs.append(f"{ctx}: '{name}' must be an integer (got {value!r})")
    return errs

def _nonneg_int(value: Any, name: str, ctx: str) -> List[str]:
    errs: List[str] = []
    try:
        iv = int(value)
        if iv < 0:
            errs.append(f"{ctx}: '{name}' must be >= 0 (got {iv})")
    except Exception:
        errs.append(f"{ctx}: '{name}' must be an integer (got {value!r})")
    return errs

def _pct(value: Any, name: str, ctx: str) -> List[str]:
    errs: List[str] = []
    try:
        fv = float(value)
        if not (0.0 <= fv <= 1.0):
            errs.append(f"{ctx}: '{name}' must be within [0,1] (got {fv})")
    except Exception:
        errs.append(f"{ctx}: '{name}' must be a float (got {value!r})")
    return errs


# ---------- Validators (existing) ----------

def validate_enemies(attacks_reg: Dict[str, Any]) -> Report:
    from core.data_loader import load_enemy_blueprints  # ensure latest
    rep = Report(errors=[], warnings=[])
    blueprints = load_enemy_blueprints(attacks_reg)

    if not blueprints:
        rep.warnings.append("No enemies found under data/enemies/.")
        return rep

    for eid, bp in blueprints.items():
        ctx = f"enemy:{eid}"
        # hp/sp
        rep.errors += _pos_int(bp.hp_max, "hp_max", ctx)
        rep.errors += _pos_int(bp.sp_max, "sp_max", ctx, zero_ok=True)
        # base stats
        for nm, val in (("attack", bp.base_stats.attack),
                        ("defense", bp.base_stats.defense),
                        ("luck", bp.base_stats.luck)):
            rep.errors += _pos_int(val, f"stats.{nm}", ctx, zero_ok=True)
        # attacks
        if not bp.attacks:
            rep.warnings.append(f"{ctx}: has no attacks; enemy will default to a weak fallback.")
        else:
            for i, atk in enumerate(bp.attacks):
                if not getattr(atk, "name", None):
                    rep.errors.append(f"{ctx}: attack at index {i} is invalid / missing in registry.")
        # weights
        if bp.attacks and len(bp.attack_weights) != len(bp.attacks):
            rep.errors.append(f"{ctx}: attack_weights length {len(bp.attack_weights)} != attacks length {len(bp.attacks)}")
        for w in bp.attack_weights:
            rep.errors += _pos_int(w, "attack_weight", ctx)
        # scaling
        for key in ("hp_per_level", "attack_per_level", "defense_per_level"):
            if key in bp.scaling:
                rep.errors += _pos_int(bp.scaling[key], f"scaling.{key}", ctx, zero_ok=True)

    return rep


def validate_encounters(blueprints: Dict[str, Any]) -> Report:
    rep = Report(errors=[], warnings=[])
    tables = load_encounter_tables()
    if not tables:
        rep.warnings.append("No encounter tables found under data/encounters/.")
        return rep

    for zone_name, buckets in tables.items():
        if zone_name not in ZONE_NAMES:
            rep.errors.append(f"encounters:{zone_name}: unknown zone; allowed={sorted(ZONE_NAMES)}")
        for bucket_name in ("normal", "boss"):
            rows = buckets.get(bucket_name, [])
            if not rows:
                rep.warnings.append(f"encounters:{zone_name}.{bucket_name}: empty list.")
                continue
            for row in rows:
                eid = str(row.get("enemy_id", ""))
                w = row.get("weight", 1)
                if not eid:
                    rep.errors.append(f"encounters:{zone_name}.{bucket_name}: missing enemy_id.")
                elif eid not in blueprints:
                    rep.errors.append(f"encounters:{zone_name}.{bucket_name}: enemy_id '{eid}' not found in enemies.")
                rep.errors += _pos_int(w, "weight", f"encounters:{zone_name}.{bucket_name}({eid})")

    return rep


def validate_equipment() -> Report:
    rep = Report(errors=[], warnings=[])
    w_bank, a_bank, r_bank = load_equipment_banks()

    def _check_factory(kind: str, fid: str, fac):
        ctx = f"equipment:{kind}:{fid}"
        try:
            obj = fac()
        except Exception as e:
            rep.errors.append(f"{ctx}: factory failed: {e}")
            return
        # durabilité
        rep.errors += _pos_int(obj.durability.maximum, "durability_max", ctx)
        rep.errors += _pos_int(obj.durability.current, "durability_current", ctx, zero_ok=True)
        if obj.durability.current > obj.durability.maximum:
            rep.errors.append(f"{ctx}: durability_current ({obj.durability.current}) > maximum ({obj.durability.maximum})")
        # bonus/percentages
        if kind == "weapon":
            rep.errors += _pos_int(getattr(obj, "bonus_attack", 0), "bonus_attack", ctx, zero_ok=True)
        elif kind == "armor":
            rep.errors += _pos_int(getattr(obj, "bonus_defense", 0), "bonus_defense", ctx, zero_ok=True)
        elif kind == "artifact":
            rep.errors += _pct(getattr(obj, "stat_percent_mod")().attack_pct, "atk_pct", ctx)
            rep.errors += _pct(getattr(obj, "stat_percent_mod")().defense_pct, "def_pct", ctx)

    for fid, fac in w_bank.items():
        _check_factory("weapon", fid, fac)
    for fid, fac in a_bank.items():
        _check_factory("armor", fid, fac)
    for fid, fac in r_bank.items():
        _check_factory("artifact", fid, fac)

    if not (w_bank or a_bank or r_bank):
        rep.warnings.append("No equipment banks found under data/equipment/ (or items\\ equipment/).")
    return rep


# ---------- NEW: Events ----------

def _validate_event_effect(payload: dict, *, ctx: str) -> List[str]:
    errs: List[str] = []
    t = payload.get("type")
    if t not in EVENT_EFFECT_TYPES:
        errs.append(f"{ctx}: unknown effect type '{t}'. allowed={sorted(EVENT_EFFECT_TYPES)}")
        return errs

    if t == "heal_hp_pct":
        errs += _pos_int(payload.get("amount_pct"), "amount_pct", ctx)
        # 1..100 (on tolère 0 si vraiment souhaité, modifie zero_ok=True)
        try:
            if not (1 <= int(payload.get("amount_pct", 0)) <= 100):
                errs.append(f"{ctx}: 'amount_pct' should be within [1,100]")
        except Exception:
            pass

    elif t == "give_gold":
        errs += _nonneg_int(payload.get("amount"), "amount", ctx)

    elif t == "damage_hp":
        errs += _pos_int(payload.get("amount"), "amount", ctx)

    elif t == "apply_effect":
        # effect_id requis, duration >=0, potency int (peut être négatif)
        eid = payload.get("effect_id")
        if not isinstance(eid, str) or not eid.strip():
            errs.append(f"{ctx}: 'effect_id' must be a non-empty string")
        errs += _nonneg_int(payload.get("duration", 0), "duration", ctx)
        # potency: int (peut être <0)
        try:
            int(payload.get("potency", 0))
        except Exception:
            errs.append(f"{ctx}: 'potency' must be an integer")

    elif t == "start_combat":
        # boss flag optionnel (bool)
        b = payload.get("boss", None)
        if b is not None and not isinstance(b, bool):
            errs.append(f"{ctx}: 'boss' must be boolean if provided")

    return errs


def validate_events() -> Report:
    """Valide data/events/ (format 'event_<zone>.json' ou anciens formats)."""
    from pathlib import Path
    import json

    rep = Report(errors=[], warnings=[])

    found_any = False
    for base in default_data_dirs():
        folder = Path(base) / "events"
        if not folder.is_dir():
            continue

        for path in folder.glob("*.json"):
            found_any = True
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                rep.errors.append(f"events:{path.name}: invalid JSON: {e}")
                continue

            file_zone = None
            events_payload: List[dict] = []

            # Format 1 (nouveau) : { "zone": "RUINS", "events": [ {...}, ... ] }
            if isinstance(raw, dict) and "events" in raw and isinstance(raw["events"], list):
                file_zone = str(raw.get("zone", "")).upper()
                if file_zone and file_zone not in ZONE_NAMES:
                    rep.errors.append(f"events:{path.name}: unknown zone '{file_zone}'; allowed={sorted(ZONE_NAMES)}")
                events_payload = list(raw["events"])

            # Format 2 : un seul event dict
            elif isinstance(raw, dict):
                events_payload = [raw]

            # Format 3 : liste d'events
            elif isinstance(raw, list):
                events_payload = raw

            else:
                rep.errors.append(f"events:{path.name}: unsupported structure (must be dict or list)")
                continue

            # Validation de chaque event
            for ev in events_payload:
                ev_id = ev.get("id", "")
                ev_ctx = f"events:{path.name}:{ev_id or 'NO_ID'}"

                # id
                if not isinstance(ev_id, str) or not ev_id.strip():
                    rep.errors.append(f"{ev_ctx}: missing/empty 'id'")

                # zone_types (si pas fourni et format 1, injecté depuis file_zone)
                zone_types = ev.get("zone_types")
                if not zone_types and file_zone:
                    zone_types = [file_zone]
                if not zone_types:
                    rep.errors.append(f"{ev_ctx}: missing 'zone_types' (and no file-level 'zone')")
                    zset = []
                else:
                    if not isinstance(zone_types, list) or not all(isinstance(z, str) for z in zone_types):
                        rep.errors.append(f"{ev_ctx}: 'zone_types' must be a list[str]")
                        zset = []
                    else:
                        zset = [z.upper() for z in zone_types]
                        for z in zset:
                            if z not in ZONE_NAMES:
                                rep.errors.append(f"{ev_ctx}: unknown zone '{z}' in zone_types; allowed={sorted(ZONE_NAMES)}")

                # weight
                w = ev.get("weight", 1)
                rep.errors += _pos_int(w, "weight", ev_ctx)

                # text.fr
                text = ev.get("text", {})
                if not (isinstance(text, dict) and isinstance(text.get("fr", ""), str) and text.get("fr", "").strip()):
                    rep.errors.append(f"{ev_ctx}: missing/empty 'text.fr'")

                # options
                options = ev.get("options", [])
                if not isinstance(options, list) or not options:
                    rep.errors.append(f"{ev_ctx}: 'options' must be a non-empty list")
                    continue

                # chaque option
                for opt in options:
                    oid = opt.get("id", "")
                    o_ctx = f"{ev_ctx}:option:{oid or 'NO_ID'}"

                    if not isinstance(oid, str) or not oid.strip():
                        rep.errors.append(f"{o_ctx}: missing/empty 'id'")

                    lab = opt.get("label", {})
                    if not (isinstance(lab, dict) and isinstance(lab.get("fr", ""), str) and lab.get("fr", "").strip()):
                        rep.errors.append(f"{o_ctx}: missing/empty 'label.fr'")

                    # requires (facultatif)
                    reqs = opt.get("requires", [])
                    if reqs is not None:
                        if not isinstance(reqs, list):
                            rep.errors.append(f"{o_ctx}: 'requires' must be a list if provided")
                        else:
                            for r in reqs:
                                if not isinstance(r, dict):
                                    rep.errors.append(f"{o_ctx}: requires entry must be an object")
                                    continue
                                st = r.get("stat")
                                if st not in REQUIRE_STATS:
                                    rep.errors.append(f"{o_ctx}: requires.stat '{st}' invalid; allowed={sorted(REQUIRE_STATS)}")
                                errs = _pos_int(r.get("gte"), "gte", o_ctx, zero_ok=True)
                                rep.errors += errs

                    # effects
                    effs = opt.get("effects", [])
                    if effs is None:
                        effs = []
                    if not isinstance(effs, list):
                        rep.errors.append(f"{o_ctx}: 'effects' must be a list")
                        effs = []
                    for i, payload in enumerate(effs):
                        if not isinstance(payload, dict):
                            rep.errors.append(f"{o_ctx}: effects[{i}] must be an object")
                            continue
                        rep.errors += _validate_event_effect(payload, ctx=f"{o_ctx}:effects[{i}]")

                    # on_fail
                    fails = opt.get("on_fail", [])
                    if fails is None:
                        fails = []
                    if not isinstance(fails, list):
                        rep.errors.append(f"{o_ctx}: 'on_fail' must be a list")
                        fails = []
                    for i, payload in enumerate(fails):
                        if not isinstance(payload, dict):
                            rep.errors.append(f"{o_ctx}: on_fail[{i}] must be an object")
                            continue
                        rep.errors += _validate_event_effect(payload, ctx=f"{o_ctx}:on_fail[{i}]")

    if not found_any:
        rep.warnings.append("No events found under data/events/.")
    return rep


def validate_all(verbose: bool = True) -> Report:
    """Valide la cohérence data globale (enemies, encounters, equipment, events)."""
    report = Report(errors=[], warnings=[])

    # Attaques (pour résolution des ids d'ennemis)
    attacks_reg = load_attacks()

    # Enemies
    enemies_rep = validate_enemies(attacks_reg)
    report.extend(enemies_rep)

    # Encounters
    enemy_bps = load_enemy_blueprints(attacks_reg)
    encounters_rep = validate_encounters(enemy_bps)
    report.extend(encounters_rep)

    # Equipment
    equip_rep = validate_equipment()
    report.extend(equip_rep)

    # Events (nouveau)
    events_rep = validate_events()
    report.extend(events_rep)

    if verbose:
        report.print()
    return report


# --- CLI ---
def main():
    rep = validate_all(verbose=True)
    raise SystemExit(0 if rep.ok() else 1)

if __name__ == "__main__":
    main()
