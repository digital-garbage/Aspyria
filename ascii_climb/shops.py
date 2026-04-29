from __future__ import annotations

import random
from typing import Tuple

from ascii_climb.loot import improve_quality, repair_cost, roll_item, sell_value
from ascii_climb.models import Item, MetaState, QUALITIES, RunState


def can_take_item(meta: MetaState, run: RunState) -> bool:
    return len(run.inventory) < meta.inventory_capacity()


def add_item_to_inventory(meta: MetaState, run: RunState, item: Item) -> Tuple[bool, str]:
    if not can_take_item(meta, run):
        return False, "Inventory is full."
    run.inventory.append(item)
    run.best_item_value = max(run.best_item_value, item.value)
    return True, f"Stored {item.label()}."


def equip_item(run: RunState, item: Item) -> str:
    old = run.equipment.get(item.slot)
    old_hp = old.stats.get("HP", 0.0) if old else 0.0
    new_hp = item.stats.get("HP", 0.0)
    if item in run.inventory:
        run.inventory.remove(item)
    run.equipment[item.slot] = item
    _adjust_current_hp_for_equipment_delta(run, new_hp - old_hp)
    if old:
        run.inventory.append(old)
        return f"Equipped {item.name}; moved {old.name} to inventory."
    return f"Equipped {item.name}."


def replace_equipped_item(run: RunState, item: Item, keep_old: bool) -> Item | None:
    old = run.equipment.get(item.slot)
    old_hp = old.stats.get("HP", 0.0) if old else 0.0
    new_hp = item.stats.get("HP", 0.0)
    if item in run.inventory:
        run.inventory.remove(item)
    run.equipment[item.slot] = item
    _adjust_current_hp_for_equipment_delta(run, new_hp - old_hp)
    if old and keep_old:
        run.inventory.append(old)
    return old


def unequip_item(meta: MetaState, run: RunState, slot: str) -> Tuple[bool, str]:
    item = run.equipment.get(slot)
    if item is None:
        return False, "No item equipped there."
    if not can_take_item(meta, run):
        return False, "Inventory is full."
    run.equipment[slot] = None
    run.inventory.append(item)
    _adjust_current_hp_for_equipment_delta(run, -item.stats.get("HP", 0.0))
    return True, f"Moved {item.name} to inventory."


def _adjust_current_hp_for_equipment_delta(run: RunState, hp_delta: float) -> None:
    if hp_delta:
        run.current_hp = max(1, int(run.current_hp + hp_delta))


def sell_item(run: RunState, item: Item) -> str:
    if item in run.inventory:
        run.inventory.remove(item)
    else:
        for slot, equipped in run.equipment.items():
            if equipped and equipped.id == item.id:
                run.equipment[slot] = None
                _adjust_current_hp_for_equipment_delta(run, -item.stats.get("HP", 0.0))
                break
    value = sell_value(item)
    run.coins += value
    return f"Sold {item.name} for {value} coins."


def drop_item(run: RunState, item: Item) -> str:
    if item in run.inventory:
        run.inventory.remove(item)
        return f"Dropped {item.name}."
    return "Item is not in inventory."


def buy_random_gear(
    rng: random.Random, meta: MetaState, run: RunState, luck: float, enemy_scaling: float
) -> Tuple[bool, str]:
    item, cost = get_or_create_random_gear_offer(rng, run, luck, enemy_scaling)
    if run.coins < cost:
        return False, f"Need {cost} coins, you have {run.coins}."
    if not can_take_item(meta, run):
        return False, "Inventory is full."
    run.coins -= cost
    if rng.random() < 0.25:
        run.random_gear_failures += 1
        bonus = run.random_gear_failures
        consume_random_gear_offer(run)
        return (
            False,
            "The merchant lowers his eyes. His caravan was attacked by necromancers "
            "and your item is lost to the void. No refunds. "
            f"Future random gear gets +{bonus}% higher-rarity and +{bonus}% higher-quality chance this run.",
        )
    run.inventory.append(item)
    run.best_item_value = max(run.best_item_value, item.value)
    consume_random_gear_offer(run)
    return True, f"Bought {item.label()} for {cost} coins."


def get_or_create_random_gear_offer(
    rng: random.Random, run: RunState, luck: float, enemy_scaling: float
) -> tuple[Item, int]:
    if run.random_gear_offer and run.random_gear_offer_cost > 0:
        return Item.from_dict(run.random_gear_offer), run.random_gear_offer_cost
    item = roll_item(
        rng,
        run,
        luck,
        enemy_scaling,
        merchant_pity=float(run.random_gear_failures),
    )
    cost = max(8, item.value)
    run.random_gear_offer = item.to_dict()
    run.random_gear_offer_cost = cost
    return item, cost


def consume_random_gear_offer(run: RunState) -> None:
    run.random_gear_offer = None
    run.random_gear_offer_cost = 0


def repair_item(run: RunState, item: Item) -> Tuple[bool, str]:
    cost = repair_cost(item)
    if cost <= 0:
        return False, f"{item.name} cannot be improved further."
    if run.coins < cost:
        return False, f"Need {cost} coins, you have {run.coins}."
    run.coins -= cost
    improve_quality(item)
    return True, f"Improved {item.name} to {item.quality} for {cost} coins."


def scouting_cost(run: RunState) -> int:
    return 10 + run.loop_tier * 6


MEDKITS = {
    "small": {"heal_fraction": 0.20, "base_cost": 20},
    "medium": {"heal_fraction": 0.50, "base_cost": 50},
    "large": {"heal_fraction": 1.00, "base_cost": 100},
}


def medkit_cost(run: RunState, size: str) -> int:
    if size not in MEDKITS:
        raise KeyError(f"Unknown medkit size: {size}")
    return int(MEDKITS[size]["base_cost"] * (2 ** run.medkits_bought))


def buy_medkit(run: RunState, max_hp: int, size: str) -> Tuple[bool, str]:
    cost = medkit_cost(run, size)
    if run.coins < cost:
        return False, f"Need {cost} coins, you have {run.coins}."
    run.coins -= cost
    run.medkits_bought += 1
    if size == "large":
        healed = max(0, max_hp - run.current_hp)
        run.current_hp = max_hp
    else:
        amount = max(1, int(max_hp * MEDKITS[size]["heal_fraction"]))
        old_hp = run.current_hp
        run.current_hp = min(max_hp, run.current_hp + amount)
        healed = run.current_hp - old_hp
    return True, f"Used {size} medkit for {cost} coins. Restored {healed} HP."


def craft_fusion(
    rng: random.Random,
    meta: MetaState,
    run: RunState,
    items: list[Item],
    luck: float,
    enemy_scaling: float,
) -> Tuple[bool, str, Item | None]:
    if len(items) < 3:
        return False, "Fusion needs three inventory items.", None
    if any(item not in run.inventory for item in items):
        return False, "Fusion can only consume inventory items.", None
    quality_indexes = [QUALITIES.index(item.quality) for item in items]
    target_index = min(len(QUALITIES) - 1, max(quality_indexes) + 1)
    target_quality = QUALITIES[target_index]
    cost = max(20, sum(item.value for item in items) // 5)
    if run.coins < cost:
        return False, f"Need {cost} coins, you have {run.coins}.", None
    for item in items:
        run.inventory.remove(item)
    run.coins -= cost
    crafted = roll_item(rng, run, luck, enemy_scaling, force_quality=target_quality)
    run.inventory.append(crafted)
    run.best_item_value = max(run.best_item_value, crafted.value)
    return True, f"Fused three items into {crafted.label()} for {cost} coins.", crafted
