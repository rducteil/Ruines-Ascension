from __future__ import annotations
"""EventEngine: charge des événements JSON, propose un choix, applique des effets.

Format JSON attendu (ex. data/events/ruins_altar_01.json):
{
  "id": "ruins_altar_01",
  "zone_types": ["RUINS"],              # si absent => tous biomes
  "weight": 8,                          # si absent => 1
  "text": { "fr": "Un autel couvert de poussière..." },
  "options": [
    {
      "id": "pray",
      "label": { "fr": "Prier" },
      "requires": [ {"stat": "luck", "gte": 10} ],    # optionnel
      "on_fail":  [ {"type": "damage_hp", "amount": 8} ],
      "effects":  [
        {"type": "heal_hp_pct", "amount_pct": 20},
        {"type": "apply_effect", "effect_id": "blessing", "duration": 2, "potency": 3}
      ]
    },
    {
      "id": "steal",
      "label": { "fr": "Voler l'offrande" },
      "effects": [ {"type": "give_gold", "amount": 25} ]
    }
  ]
}
"""

import json, os, random
from dataclasses import dataclass
from typing import Any, Callable, Sequence, TYPE_CHECKING
from pathlib import Path

from core.combat import CombatEvent, CombatContext, CombatResult
from core.data_paths import default_data_dirs
from core.effects_bank import make_effect

if TYPE_CHECKING:
    from core.player import Player
    from core.effects import Effect
    from core.effect_manager import EffectManager

# Types légers
@dataclass
class EventOption:
    id: str
    label: str
    raw: dict

@dataclass
class LoadedEvent:
    id: str
    text: str
    options: list[EventOption]
    zone_types: list[str]
    weight: int
    raw: dict


@dataclass
class EventApplyResult:
    events: list[CombatEvent]
    start_combat: dict | None = None  # ex: {"enemy_id": "mini_boss"} ou {"boss": True}


class EventEngine:
    """Charge et résout des événements.

    - data_dir : dossier qui contient des .json (un évènement par fichier)
    - lang    : langue de rendu pour text/labels ("fr" par défaut)
    - effects : EffectManager pour appliquer des effets persistants
    - enemy_factory: callable facultative pour créer un ennemi à partir d'un id (si start_combat)
    """

    def __init__(
        self,
        data_dir: str = "data",
        *,
        lang: str = "fr",
        seed: int | None = None,
        effects: EffectManager | None = None,
        enemy_factory: Callable[[dict], Any] | None = None,  # reçoit dict effect {"enemy_id":..., "boss":...}
    ) -> None:
        self.lang = lang
        self.rng = random.Random(seed)
        self.effects = effects
        self.enemy_factory = enemy_factory
        self._events: list[LoadedEvent] = []
        self._load_from_dir(data_dir)

    # --------- Chargement ---------

    def _load_from_dir(self, data_dir: str) -> None:
        """
        Cherche un dossier 'events' sous plusieurs bases possibles, puis charge tous les JSON.
        """
        here = Path(__file__).resolve()

        # Candidats possibles selon ta structure:
        # - data_dir relatif au CWD (ex: lancer depuis la racine)
        # - data_dir relatif à src/ (là où se trouve event_engine.py)
        # - data_dir relatif à la racine du repo (src/..)
        candidates = []
        if data_dir:
            candidates += [
                Path(data_dir),                         # .\data
                here.parent / data_dir,                # src/core + data -> src/core/data (souvent vide)
                here.parent.parent / data_dir,         # src/data           ✅
                here.parent.parent.parent / data_dir,  # racine/data        (si tu déplaces data)
            ]
        else:
            # fallback si aucun data_dir n'est passé : utilise tes chemins par défaut
            candidates = default_data_dirs()

        base = None
        for c in candidates:
            if (c / "events").is_dir():
                base = c
                break
        if base is None:
            # rien trouvé, on quitte proprement
            return

        folder = base / "events"
        # (optionnel) debug:
        # print(f"[DEBUG] EventEngine: folder={folder}")

        for path in folder.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))

                # Format A: pack par zone { "zone": "...", "events": [...] }
                if isinstance(raw, dict) and "events" in raw and isinstance(raw["events"], list):
                    zone_name = str(raw.get("zone", "")).strip().lower()
                    for ev_raw in raw["events"]:
                        ev_raw = dict(ev_raw)
                        if "zone_types" not in ev_raw and zone_name:
                            ev_raw["zone_types"] = [zone_name]
                        # ceinture & bretelles : normaliser si déjà présent
                        if "zone_types" in ev_raw:
                            ev_raw["zone_types"] = [str(z).strip().lower() for z in ev_raw["zone_types"]]
                        ev = self._parse_event(ev_raw)
                        self._events.append(ev)
                    continue

                # Format B: liste d'events dans le fichier
                if isinstance(raw, list):
                    for ev_raw in raw:
                        ev = self._parse_event(ev_raw)
                        self._events.append(ev)
                else:
                    ev = self._parse_event(raw)
                    self._events.append(ev)

            except Exception:
                continue

    def register_event(self, raw: dict) -> None:
        """Permet d'injecter un évènement (utile en tests)."""
        self._events.append(self._parse_event(raw))

    def _parse_event(self, raw: dict) -> LoadedEvent:
        text = self._loc(raw.get("text"), self.lang, default="[missing text]")
        opts = []
        for o in raw.get("options", []):
            label = self._loc(o.get("label"), self.lang, default=o.get("id", "?"))
            opts.append(EventOption(id=o.get("id", "?"), label=label, raw=o))
        zone_types = [str(z).strip().lower() for z in raw.get("zone_types", [])]
        weight = int(raw.get("weight", 1))
        return LoadedEvent(
            id=raw.get("id", "event"),
            text=text,
            options=opts,
            zone_types=zone_types,
            weight=max(1, weight),
            raw=raw,
        )

    def _loc(self, obj: Any, lang: str, default: str) -> str:
        if isinstance(obj, dict):
            return str(obj.get(lang, default))
        if isinstance(obj, str):
            return obj
        return default

    # --------- Sélection ---------

    def pick_for_zone(self, zone_type: str) -> LoadedEvent | None:
        """Tire un évènement compatible avec le biome, selon weight."""
        z = str(zone_type).strip().lower() 
        pool = [e for e in self._events if (not e.zone_types or z in e.zone_types)]
        if not pool:
            return None
        total_w = sum(e.weight for e in pool)
        r = self.rng.uniform(0, total_w)
        acc = 0.0
        for e in pool:
            acc += e.weight
            if r <= acc:
                return e
        return pool[-1]

    # --------- Application ---------

    def apply_option(
    self,
    event: LoadedEvent,
    option_id: str,
    *,
    player: Player,
    wallet: Any | None = None,
    extra_ctx: dict | None = None,  # ex: {"zone": zone_obj}
) -> EventApplyResult:
        """Applique les effets de l'option (ou on_fail si requirements non remplis)."""
        # 1) Retrouver l’option choisie
        opt = next((o for o in event.options if o.id == option_id), None)
        if opt is None:
            return EventApplyResult(events=[CombatEvent(text="Option invalide.", tag="event_error")])

        # 2) Contexte minimal pour logs/effects
        logs: list[CombatEvent] = []
        ctx = CombatContext(attacker=player, defender=None, events=logs)

        # 3) Vérifier les prérequis (sinon on_fail)
        if not self._requirements_met(opt.raw.get("requires", []), player):
            for eff in opt.raw.get("on_fail", []):
                self._apply_effect_payload(eff, player, wallet, ctx, extra_ctx)
            if not opt.raw.get("on_fail"):
                logs.append(CombatEvent(text="Tu n'as pas les prérequis pour cette option.", tag="event_requires"))
            return EventApplyResult(events=logs)

        # 4) Appliquer les effets de l’option
        pending_combat: dict | None = None
        for eff in opt.raw.get("effects", []):
            # Cas particulier: déclenchement d’un combat (le GameLoop interprètera)
            if isinstance(eff, dict) and eff.get("type") == "start_combat":
                # ex: {"enemy_id": "..."} ou {"boss": true}
                pending_combat = eff
                continue
            # Dispatcher data-driven (heal/damage/gold/apply_effect/etc.)
            self._apply_effect_payload(eff, player, wallet, ctx, extra_ctx)

        # 5) Retourne les logs + éventuel ordre de combat à démarrer
        return EventApplyResult(events=logs, start_combat=pending_combat)


    def _requirements_met(self, reqs: Sequence[dict], player: Any) -> bool:
        """Actuellement: seuils sur les stats (gte/lte). S'étend facilement (items, or...)."""
        for r in reqs:
            stat = r.get("stat")
            gte = r.get("gte")
            lte = r.get("lte")
            val = getattr(getattr(player, "base_stats", player), str(stat), None)
            if val is None:
                return False
            if gte is not None and not (val >= int(gte)):
                return False
            if lte is not None and not (val <= int(lte)):
                return False
        return True

    # ---- Dispatch d'effets data-driven ----

    def _apply_effect_payload(
        self,
        eff: dict,
        player: Player,
        wallet: Any | None,
        ctx: CombatContext,
        extra_ctx: dict | None,
    ) -> None:
        t = eff.get("type")
        if t == "heal_hp":
            amount = int(eff.get("amount", 0))
            healed = player.heal_hp(amount)
            ctx.events.append(CombatEvent(text=f"{player.name} récupère {healed} PV.", tag="heal_hp"))
            return
        if t == "heal_hp_pct":
            pct = int(eff.get("amount_pct", 0))
            healed = player.heal_hp(int(player.max_hp * pct / 100))
            ctx.events.append(CombatEvent(text=f"{player.name} récupère {healed} PV ({pct}%).", tag="heal_hp_pct"))
            return
        if t == "damage_hp":
            amount = int(eff.get("amount", 0))
            taken = player.take_damage(amount)
            ctx.events.append(CombatEvent(text=f"{player.name} subit {taken} dégâts.", tag="damage_hp"))
            return
        if t == "restore_sp":
            amount = int(eff.get("amount", 0))
            got = player.heal_sp(amount)
            ctx.events.append(CombatEvent(text=f"{player.name} récupère {got} SP.", tag="restore_sp"))
            return
        if t == "give_gold" and wallet is not None:
            amt = int(eff.get("amount", 0))
            wallet.add(amt)
            ctx.events.append(CombatEvent(text=f"+{amt} or.", tag="gold_gain"))
            return
        if t == "take_gold" and wallet is not None:
            amt = int(eff.get("amount", 0))
            if wallet.spend(amt):
                ctx.events.append(CombatEvent(text=f"-{amt} or.", tag="gold_spend"))
            else:
                ctx.events.append(CombatEvent(text=f"Impossible de payer {amt} or.", tag="gold_fail"))
            return
        if t == "apply_effect" and self.effects is not None:
            # Applique un Effect persistant référencé par un registry
            eff_id = eff.get("effect_id")
            duration = int(eff.get("duration", 0))
            potency = int(eff.get("potency", 0))
            try:
                new_effs: list[Effect] = make_effect(eff_id, duration=duration, potency=potency)
            except KeyError:
                ctx.events.append(CombatEvent(text=f"Échec: effet inconnu '{eff_id}'.", tag="apply_effect_fail"))
                return
            if not new_effs:
                ctx.events.append(CombatEvent(text=f"Échec: effet inconnu '{eff_id}'.", tag="apply_effect_fail"))
                return
            
            for new_eff in new_effs:
                try:
                    self.effects.apply(player, new_eff, source_name=f"event:{eff_id}", ctx=ctx, max_stacks=1)
                    ctx.events.append(CombatEvent(text=f"Effet {new_eff.name} appliqué.", tag="apply_effect"))
                except Exception:
                    ctx.events.append(CombatEvent(text=f"Échec: effet inconnu '{eff_id}'.", tag="apply_effect_fail"))
            return
        # Inconnu → log
        ctx.events.append(CombatEvent(text=f"(Effet inconnu ignoré: {t})", tag="event_unknown"))
