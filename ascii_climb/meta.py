from __future__ import annotations

import math
from typing import Dict, Tuple

from ascii_climb.content import BASE_STATS, SETS, UPGRADE_BASE_COSTS
from ascii_climb.ilevel import gear_advantage_bonuses
from ascii_climb.models import MetaState, PERMANENT_ONLY_STAT_KEYS, RunState, STAT_KEYS, blank_stats
from ascii_climb.relics import apply_passive_relics
from ascii_climb.state import clamp_effective_stats, sanitize_run_state

MAX_UPGRADE_LEVEL = 50
MAX_EXTRA_INVENTORY_SLOTS = 40
FIRST_EXTRA_SLOT_COST = 25
SLOT_COST_MULTIPLIER = 1.35


def upgrade_bonus_for_level(level: int) -> int:
    level = max(0, int(level))
    return level + level // 5


def upgrade_cost(stat: str, next_level: int) -> int:
    if stat not in UPGRADE_BASE_COSTS:
        raise KeyError(f"Unknown stat: {stat}")
    if next_level < 1:
        raise ValueError("Upgrade level starts at 1")
    return int(round(UPGRADE_BASE_COSTS[stat] * (1.22 ** (next_level - 1))))


def buy_upgrade(meta: MetaState, stat: str) -> Tuple[bool, str]:
    current = meta.upgrades.get(stat, 0)
    if current >= MAX_UPGRADE_LEVEL:
        return False, f"{stat} is already maxed."
    cost = upgrade_cost(stat, current + 1)
    if meta.gold < cost:
        return False, f"Need {cost} gold, you have {meta.gold}."
    meta.gold -= cost
    meta.upgrades[stat] = current + 1
    return True, f"{stat} upgraded to level {current + 1}."


def refund_upgrade(meta: MetaState, stat: str) -> Tuple[bool, str]:
    current = meta.upgrades.get(stat, 0)
    if current <= 0:
        return False, f"{stat} has nothing to refund."
    original_cost = upgrade_cost(stat, current)
    refund = original_cost // 2
    meta.gold += refund
    meta.upgrades[stat] = current - 1
    return True, f"Refunded {stat} level {current} for {refund} gold."


def inventory_slot_cost(next_slot_number: int) -> int:
    if next_slot_number < 1:
        raise ValueError("Slot purchase number starts at 1")
    return math.ceil(FIRST_EXTRA_SLOT_COST * (SLOT_COST_MULTIPLIER ** (next_slot_number - 1)))


def buy_inventory_slot(meta: MetaState) -> Tuple[bool, str]:
    current = meta.inventory_slots_purchased
    if current >= MAX_EXTRA_INVENTORY_SLOTS:
        return False, "Inventory slots are already maxed."
    cost = inventory_slot_cost(current + 1)
    if meta.gold < cost:
        return False, f"Need {cost} gold, you have {meta.gold}."
    meta.gold -= cost
    meta.inventory_slots_purchased += 1
    return True, f"Inventory capacity is now {meta.inventory_capacity()}."


def refund_inventory_slot(meta: MetaState) -> Tuple[bool, str]:
    current = meta.inventory_slots_purchased
    if current <= 0:
        return False, "No purchased inventory slots to refund."
    refund = inventory_slot_cost(current) // 2
    meta.gold += refund
    meta.inventory_slots_purchased -= 1
    return True, f"Refunded one inventory slot for {refund} gold."


def permanent_bonuses(meta: MetaState) -> Dict[str, float]:
    bonuses = blank_stats()
    for stat in STAT_KEYS:
        bonuses[stat] = float(upgrade_bonus_for_level(meta.upgrades.get(stat, 0)))
    return bonuses


def set_bonuses(run: RunState) -> Dict[str, float]:
    bonuses: Dict[str, float] = {}
    equipped = run.equipped_items()
    for set_name, definition in SETS.items():
        pieces = [
            item
            for item in equipped
            if item.set_name == set_name and item.slot in definition.required_slots
        ]
        unique_slots = {item.slot for item in pieces}
        if unique_slots == set(definition.required_slots):
            for stat, amount in definition.full_bonuses.items():
                bonuses[stat] = bonuses.get(stat, 0.0) + amount
        else:
            amount = len(unique_slots) * definition.partial_bonus
            if amount:
                bonuses[definition.partial_stat] = bonuses.get(definition.partial_stat, 0.0) + amount
    return bonuses


def effective_stats(meta: MetaState, run: RunState) -> Dict[str, float]:
    sanitize_run_state(run)
    apply_passive_relics(run)
    stats = dict(BASE_STATS)
    item_totals = blank_stats()
    for item in run.equipped_items():
        for stat, amount in item.stats.items():
            if stat in PERMANENT_ONLY_STAT_KEYS:
                continue
            item_totals[stat] = item_totals.get(stat, 0.0) + amount

    permanent = permanent_bonuses(meta)
    for stat in STAT_KEYS:
        if stat in {"ATK", "HP"}:
            base_with_items = stats[stat] + item_totals.get(stat, 0.0)
            level_bonus = 1 + max(0, run.level - 1) * 0.06
            stats[stat] = base_with_items * level_bonus * (1 + permanent.get(stat, 0.0) / 100)
        else:
            stats[stat] = stats.get(stat, 0.0) + item_totals.get(stat, 0.0) + permanent.get(stat, 0.0)

    for stat, amount in set_bonuses(run).items():
        if stat in PERMANENT_ONLY_STAT_KEYS:
            continue
        stats[stat] = stats.get(stat, 0.0) + amount

    for stat, amount in gear_advantage_bonuses(run).items():
        if stat in PERMANENT_ONLY_STAT_KEYS:
            continue
        stats[stat] = stats.get(stat, 0.0) + amount

    for stat, amount in run.run_buffs.items():
        if stat in PERMANENT_ONLY_STAT_KEYS:
            continue
        stats[stat] = stats.get(stat, 0.0) + amount

    for stat, amount in run.run_debuffs.items():
        if stat in PERMANENT_ONLY_STAT_KEYS:
            continue
        stats[stat] = max(0.0, stats.get(stat, 0.0) - amount)

    for modifier in run.timed_stat_modifiers:
        stat = modifier.get("stat")
        if stat in stats:
            stats[stat] *= float(modifier.get("multiplier", 1.0))

    return clamp_effective_stats(stats)


def boss_gold_for_index(index: int) -> int:
    if index < 1:
        return 0
    return int(round(25 * (1.5 ** (index - 1))))


def final_gold_payout(meta: MetaState, run: RunState) -> int:
    boss_gold = sum(boss_gold_for_index(i) for i in range(1, run.completed_bosses + 1))
    depth_gold = (run.loop_tier - 1) * 120 + run.location_index * 20
    enemy_gold = run.strongest_enemy_power // 10
    item_gold = run.best_item_value // 30
    corrupted_gold = run.corrupted_kills * 18
    equipped_gold = int(run.average_ilevel() * 3)
    subtotal = boss_gold + depth_gold + enemy_gold + item_gold + corrupted_gold + equipped_gold

    stats = effective_stats(meta, run)
    greed_bonus = (
        stats.get("Enemy Scaling%", 0.0)
        + stats.get("Gold Payout%", 0.0)
        + stats.get("Gold Acquisition Boost%", 0.0)
    )
    return max(1, int(round(subtotal * (1 + greed_bonus / 100))))
