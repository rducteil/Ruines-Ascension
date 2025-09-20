from __future__ import annotations
"""I/O console (texte) pour piloter GameLoop, uniquement pour tests/dev."""

from typing import TYPE_CHECKING
from collections.abc import Sequence
from time import sleep

from core.supply import Wallet
from content.shop_offers import ShopOffer
from game.game_loop import Section, SectionType, Zone, ZoneType

if TYPE_CHECKING:
    from core.player import Player
    from core.enemy import Enemy
    from core.attack import Attack
    from core.inventory import Inventory
    from core.combat import CombatResult, CombatEngine

class ConsoleIO:
    """Implémentation texte des callbacks I/O utilisés par GameLoop."""

    # ---------- Combats ----------

    def on_battle_start(self, player: Player, enemy: Enemy) -> None:
        is_boss = getattr(enemy, "is_boss", False)
        print(f"\n=== COMBAT: {player.name} vs {enemy.name} ===")
        if is_boss:
            print("        ⚔️  B O S S  ⚔️\n\n")
        print(enemy)
        sleep(1)

    def present_events(self, result: CombatResult) -> None:
        # result est un CombatResult (type importé par GameLoop)
        for ev in result.events:
            print(" -", ev.text)

    def show_status(self, player: Player, enemy: Enemy) -> None:
        print(f"   PV {player.name}: {player.hp}/{player.max_hp}  |  PV {enemy.name}: {enemy.hp}/{enemy.max_hp}")
        print(f"   SP {player.name}: {player.sp}/{player.max_sp}  |")

    def on_battle_end(self, player: Player, enemy: Enemy, victory: bool) -> None:
        msg = f"Victoire ! {enemy.name} est vaincu." if victory else f"Défaite… {player.name} tombe au combat."
        print(msg)
        sleep(1)

    def choose_player_action(self, player: Player, enemy: Enemy, *, attacks: list[Attack], inventory: Inventory, engine: CombatEngine):
        act = True
        sleep(0.5)
        while act:
            print("\nChoisis une action :")
            print("  1) Attaquer")
            print("  2) Objet")
            c = self._ask_index(2)

            if c == 0:
                # Utiliser la liste "attacks" passée par GameLoop
                print(f"\nChoisis une attaque (STA : {player.sp}/{player.max_sp}):")
                for i, a in enumerate(attacks, 1):
                    if not getattr(a, "deal_damage", True):
                        label = f"{a.name} (utilitaire, SP {a.cost})"
                    else:
                        lo, hi = engine.estimate_damage(player, enemy, a)
                        label = f"  {i}) {a.name} (≈{lo}–{hi}, SP {a.cost})"
                    print(label)
                    nm = getattr(a, "name", "???")
                    cost = getattr(a, "cost", 0)
                    dmg  = getattr(a, "base_damage", 0)
                    var  = getattr(a, "variance", 0)
                    print(f"  {i}) {nm} (Dmg {dmg}±{var}, SP {cost})")
                idx = self._ask_index(len(attacks))
                sleep(0.5)
                return ("attack", attacks[idx])
            elif c == 1:
                # Objet
                items = [row for row in inventory.list_summary() if row["kind"] == "item"]
                if not items:
                    print("   Aucun objet utilisable")
                print("Objets :")
                for i, it in enumerate(items, 1):
                    print(f"  {i}) {it['name']} x{it['qty']}")
                idx = self._ask_index(len(items))
                item_id = items[idx]["id"]
                sleep(0.5)
                return ("item", item_id)         

    # ---------- Zones / Sections ----------

    def on_zone_start(self, zone: Zone) -> None:
        print(f"\n=== Entrée dans la zone: {zone.zone_type.name} (Niveau {zone.level}) ===")
        sleep(1)

    def on_zone_cleared(self, zone: Zone) -> None:
        print(f"=== Zone {zone.zone_type.name} nettoyée ! ===")
        sleep(1)

    def choose_section(self, zone: Zone, options: Sequence[Section]) -> Section:
        """Propose 2 sections de types différents et renvoie le choix de l’utilisateur."""
        print("\nProchaine section :")
        sleep(0.2)
        for i, s in enumerate(options, start=1):
            label = self._label_section(s.kind)
            print(f"  {i}) {label}")
        idx = self._ask_index(len(options))
        sleep(1)
        return options[idx]

    def choose_supply_action(self, player: Player, *, wallet: Wallet, offers: ShopOffer):
        print(f"HP : {player.hp}/{player.max_hp}\n", f"STA : {player.sp}/{player.max_sp}\n")
        print(f"\n-- Ravitaillement -- Or: {wallet.gold}")
        print("  1) Se reposer")
        print("  2) Réparer (tout ce qu’on peut)")
        print("  3) Boutique")
        print("  4) Sauvegarder")
        print("  5) Charger")
        print("  6) Quitter")
        idx = self._ask_index(6)
        return ["REST","REPAIR","SHOP","SAVE", "LOAD", "LEAVE"][idx]

    def choose_shop_purchase(self, offers: list[ShopOffer], *, wallet:Wallet):
        print(f"\nBoutique (or: {wallet.gold})")
        for i, off in enumerate(offers, 1):
            label = off.name if off.kind != "item" else f"{off.name} ({off.item_id})"
            print(f"  {i}) {label} — {off.price} or")
        print("  0) Retour")
        raw = input("> Choix: ").strip()
        if raw == "0":
            return None
        try:
            idx = int(raw) - 1
            off = offers[idx]
        except Exception:
            return None
        qty = 1
        if off.kind == "item":
            q = input("> Quantité (défaut 1): ").strip()
            if q.isdigit():
                qty = max(1, int(q))
        return (off, qty)

    def choose_event_option(self, text: str, options: Sequence[str]):
        print("\n-- Évènement --")
        print(text)
        for i, label in enumerate(options, 1):
            print(f"  {i}) {label}")
        idx = self._ask_index(len(options))
        return idx  # renvoie l'index; le GameLoop convertit en id

    def choose_next_zone(self, options: Sequence[ZoneType]) -> ZoneType:
        """Après un boss vaincu, choisir la prochaine zone parmi 3 options."""
        print("\nChoisis la prochaine zone :")
        for i, z in enumerate(options, start=1):
            print(f"  {i}) {z.name}")
        idx = self._ask_index(len(options))
        return options[idx]

    # ---------- Helpers ----------

    def _label_section(self, kind: SectionType) -> str:
        return {
            SectionType.COMBAT: "Combat",
            SectionType.EVENT: "Événement",
            SectionType.SUPPLY: "Ravitaillement",
            SectionType.BOSS: "Boss",
        }[kind]

    def _ask_index(self, length: int) -> int:
        """Demande un index utilisateur (1..length) et renvoie l’indice 0-based."""
        while True:
            raw = input("> Choix: ").strip()
            if not raw.isdigit():
                print("Entrée invalide. Tape un nombre.")
                continue
            i = int(raw)
            if 1 <= i <= length:
                return i - 1
            print(f"Choisis un nombre entre 1 et {length}.")

    def present_text(self, text: str) -> None:
        print(text)