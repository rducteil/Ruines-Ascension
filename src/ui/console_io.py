from __future__ import annotations
"""I/O console (texte) pour piloter GameLoop, uniquement pour tests/dev."""

from typing import List, Sequence, Optional

from core.player import Player
from core.enemy import Enemy
from core.attack import Attack
from core.wallet import Wallet
from content.shop_offers import ShopOffer

# On importe uniquement les types "simples" depuis game_loop
from game.game_loop import Section, SectionType, Zone, ZoneType


class ConsoleIO:
    """Implémentation texte des callbacks I/O utilisés par GameLoop."""

    # ---------- Combats ----------

    def on_battle_start(self, player: Player, enemy: Enemy) -> None:
        print(f"\n=== COMBAT: {player.name} vs {enemy.name} ===")

    def present_events(self, result) -> None:
        # result est un CombatResult (type importé par GameLoop)
        for ev in result.events:
            print(" -", ev.text)

    def show_status(self, player: Player, enemy: Enemy) -> None:
        print(f"   PV {player.name}: {player.hp}/{player.max_hp}  |  PV {enemy.name}: {enemy.hp}/{enemy.max_hp}")
        # Si tu as des SP visibles :
        if hasattr(player, "sp") and hasattr(player, "max_sp"):
            print(f"   SP {player.name}: {player.sp}/{player.max_sp}")

    def on_battle_end(self, player: Player, enemy: Enemy, victory: bool) -> None:
        msg = f"Victoire ! {enemy.name} est vaincu." if victory else f"Défaite… {player.name} tombe au combat."
        print(msg)

    def choose_player_action(self, player, enemy, *, attacks, inventory):
        print("\nChoisis une action :")
        print("  1) Attaquer")
        print("  2) Objet")
        c = self._ask_index(2)
        if c == 0:
            # Menu d'attaque (ici un seul pour l’exemple, ou ton loadout)
            return ("attack", attacks[0])
        # Objet
        items = [row for row in inventory.list_summary() if row["kind"] == "item"]
        if not items:
            print("   (Aucun objet utilisable) → Attaque par défaut.")
            return ("attack", attacks[0])
        print("Objets :")
        for i, it in enumerate(items, 1):
            print(f"  {i}) {it['name']} x{it['qty']}")
        idx = self._ask_index(len(items))
        item_id = items[idx]["id"]
        return ("item", item_id)

    def choose_player_attack(self, player: Player, enemy: Enemy, options=None) -> Attack:
        """Menu simple: attaques d’arme spéciales + éventuelle attaque de classe + attaque basique."""
        if options is None:
            options: List[Attack] = []

            # 1) attaques spéciales de l'arme si dispo
            weapon = getattr(player, "weapon", None)
            if weapon and hasattr(weapon, "get_available_attacks"):
                specials = weapon.get_available_attacks()  # type: ignore[attr-defined]
                if specials:
                    options.extend(specials)

            # 2) attaque de classe si dispo
            class_attack = getattr(player, "class_attack", None)
            if class_attack:
                options.append(class_attack)

            # 3) attaque basique par défaut (toujours disponible)
            basic = Attack(name="Attaque basique", base_damage=5, variance=2, cost=0)
            options.append(basic)

            # Affichage menu
            print("\nChoisis une attaque :")
            for idx, atk in enumerate(options, start=1):
                cost = getattr(atk, "cost", 0)
                dmg = getattr(atk, "base_damage", 0)
                var = getattr(atk, "variance", 0)
                print(f"  {idx}) {atk.name}  (Dmg {dmg}±{var}, Cost SP {cost})")

            choice = self._ask_index(len(options))
            return options[choice]
        print("\nChoisis une action : ")
        for i, atk in enumerate(options, 1):
            print(f"    {i}) {atk.name} (Dmg {atk.base_damage}±{atk.variance}, SP {atk.cost})")
        idx = self._ask_index(len(options))
        return options[idx]

    # ---------- Zones / Sections ----------

    def on_zone_start(self, zone: Zone) -> None:
        print(f"\n=== Entrée dans la zone: {zone.zone_type.name} (Niveau {zone.level}) ===")

    def on_zone_cleared(self, zone: Zone) -> None:
        print(f"=== Zone {zone.zone_type.name} nettoyée ! ===")

    def choose_section(self, zone: Zone, options: Sequence[Section]) -> Section:
        """Propose 2 sections de types différents et renvoie le choix de l’utilisateur."""
        print("\nProchaine section :")
        for i, s in enumerate(options, start=1):
            label = self._label_section(s.kind)
            print(f"  {i}) {label}")
        idx = self._ask_index(len(options))
        return options[idx]

    def choose_supply_action(self, player, *, wallet: Wallet, offers):
        print(f"\n-- Ravitaillement -- Or: {wallet.gold}")
        print("  1) Se reposer")
        print("  2) Réparer (tout ce qu’on peut)")
        print("  3) Boutique")
        print("  4) Quitter")
        idx = self._ask_index(4)
        return ["REST","REPAIR","SHOP","LEAVE"][idx]

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
