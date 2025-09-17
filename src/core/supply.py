from __future__ import annotations
"""Logique de ravitaillement: repos, réparation, achats, parchemin de classe."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.combat import CombatEvent
from content.items import make_item
from content.actions import with_class_attack        # pour mettre l’attaque de classe dans le loadout
from content import shop_offers                      # REST/REPAIR defaults

if TYPE_CHECKING:
    from core.player import Player
    from core.equipment import Equipment
    from core.attack import Attack
    from core.inventory import Inventory
    from content.shop_offers import ShopOffer
    from core.loadout import LoadoutManager


class Wallet:
    """Porte-monnaie simple (or)."""
    def __init__(self, gold: int = 0) -> None:
        self._gold = max(0, int(gold))

    @property
    def gold(self) -> int:
        return self._gold

    def add(self, amount: int) -> int:
        amount = int(amount)
        if amount <= 0: return 0
        self._gold += amount
        return amount

    def can_afford(self, amount: int) -> bool:
        return self._gold >= max(0, int(amount))

    def spend(self, amount: int) -> bool:
        amount = int(amount)
        if amount <= 0 or self._gold < amount: return False
        self._gold -= amount
        return True

@dataclass
class SupplyResult:
    events: list[CombatEvent]
    spent: int = 0
    ok: bool = True
    note: str = ""

class SupplyManager:
    def __init__(self, inventory: Inventory, wallet: Wallet, loadouts: LoadoutManager) -> None:
        self.inventory = inventory
        self.wallet = wallet
        self.loadouts = loadouts

    # --- REST ---
    def do_rest(self, player: Player, *, hp_pct: int = shop_offers.REST_HP_PCT, sp_pct: int = shop_offers.REST_SP_PCT) -> SupplyResult:
        ev: list[CombatEvent] = []
        healed_hp = player.heal_hp(int(player.max_hp * hp_pct / 100))
        healed_sp = player.heal_sp(int(player.max_sp * sp_pct / 100))
        if healed_hp or healed_sp:
            msg = f"{player.name} se repose (+{healed_hp} PV, +{healed_sp} SP)."
        else:
            msg = f"{player.name} se repose, mais n’en tire aucun bénéfice."
        ev.append(CombatEvent(text=msg, tag="rest"))
        return SupplyResult(events=ev)

    # --- REPAIR ---
    def repair_all_you_can_afford(self, player, price_per_point: int = shop_offers.REPAIR_COST_PER_POINT) -> SupplyResult:
        ev: list[CombatEvent] = []
        spent = 0

        # On répare weapon + armor si présents
        for slot in ("weapon", "armor"):
            eq: Equipment = getattr(player, slot, None)
            if not eq:
                continue
            need = eq.durability.maximum - eq.durability.current
            if need <= 0:
                continue
            # combien on peut payer ?
            max_pts = self.wallet.gold // price_per_point
            if max_pts <= 0:
                continue
            pts = min(need, max_pts)
            cost = pts * price_per_point
            if not self.wallet.spend(cost):
                continue
            eq.repair(pts)
            spent += cost
            ev.append(CombatEvent(text=f"Réparation de {eq.name}: +{pts} durabilité (coût {cost} or).", tag="repair"))

        if spent == 0:
            ev.append(CombatEvent(text="Aucune réparation effectuée (fonds insuffisants ou déjà au max).", tag="repair_none"))
            return SupplyResult(events=ev, spent=0, ok=False)
        return SupplyResult(events=ev, spent=spent)

    # --- SHOP purchase ---
    def buy_offer(self, player: Player, offer: ShopOffer, *, qty: int = 1) -> SupplyResult:
        ev: list[CombatEvent] = []
        qty = max(1, int(qty))

        if offer.kind == "item" and offer.item_id:
            total = offer.price * qty
            if not self.wallet.spend(total):
                return SupplyResult(events=[CombatEvent(text="Fonds insuffisants.", tag="shop_fail")], ok=False)
            added = self.inventory.add_item(make_item(offer.item_id), qty=qty)
            ev.append(CombatEvent(text=f"Achat: {offer.name} x{added} (coût {total} or).", tag="shop_buy"))
            if added < qty:
                ev.append(CombatEvent(text="Inventaire plein: une partie de l’achat a été perdue.", tag="inv_full"))
            return SupplyResult(events=ev, spent=total, ok=(added > 0))

        if offer.kind == "class_scroll":
            # On remplace le slot 'skill' du loadout par l’attaque de classe du joueur
            # On récupère l’attaque de classe depuis le registre contenu -> player class
            class_key = offer.class_key or getattr(player, "player_class_key", None)
            if not class_key:
                return SupplyResult(events=[CombatEvent(text="Aucune classe détectée.", tag="shop_fail")], ok=False)

            # Récupère l'attaque de classe depuis le registre (content.player_classes ou core fallback)
            try:
                from content.player_classes import CLASSES as PCONTENT
                pclass = PCONTENT.get(class_key)
            except Exception:
                pclass = None
            if pclass is None:
                try:
                    from content.player_classes import CLASSES as PCORE
                    pclass = PCORE.get(class_key)
                except Exception:
                    pclass = None
            class_attack: Attack = getattr(pclass, "class_attack", None) if pclass else None
            if class_attack is None:
                return SupplyResult(events=[CombatEvent(text="Cette classe n’a pas d’attaque de classe définie.", tag="shop_fail")], ok=False)

            if not self.wallet.spend(offer.price):
                return SupplyResult(events=[CombatEvent(text="Fonds insuffisants.", tag="shop_fail")], ok=False)

            lo = self.loadouts.get(player)
            if lo is None:
                return SupplyResult(events=[CombatEvent(text="Loadout introuvable.", tag="shop_fail")], ok=False)
            upgraded = with_class_attack(lo, class_attack)
            self.loadouts.set(player, upgraded)
            ev.append(CombatEvent(text=f"{player.name} apprend {class_attack.name} !", tag="class_scroll"))
            return SupplyResult(events=ev, spent=offer.price)

        return SupplyResult(events=[CombatEvent(text="Offre invalide.", tag="shop_invalid")], ok=False)


