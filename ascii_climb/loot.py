from __future__ import annotations

import random
from typing import List, Sequence, Tuple

from ascii_climb.content import (
    LOCATIONS,
    QUALITY_MULTIPLIERS,
    RARITY_MULTIPLIERS,
    RARITY_NAMES,
    RELICS,
    SETS,
    SLOT_NAMES,
    SLOT_STAT_POOLS,
)
from ascii_climb.ilevel import roll_location_ilevel
from ascii_climb.models import EQUIPMENT_SLOTS, PERMANENT_ONLY_STAT_KEYS, QUALITIES, RARITIES, STAT_KEYS, Item, RunState


ITEM_PRICE_BASE = 14
SELL_VALUE_RATE = 0.34
CARAVAN_BUY_RATE = 1.18
IMPROVEMENT_RATE = 0.42


def weighted_choice(rng: random.Random, weighted_items: Sequence[Tuple[str, float]]) -> str:
    total = sum(weight for _, weight in weighted_items)
    point = rng.uniform(0, total)
    upto = 0.0
    for item, weight in weighted_items:
        upto += weight
        if point <= upto:
            return item
    return weighted_items[-1][0]


def corrupted_chance_percent(
    luck: float, enemy_scaling: float, loop_tier: int, merchant_pity: float = 0.0
) -> float:
    pressure = enemy_scaling * 0.04 + (loop_tier - 1) * 0.55
    return min(28.0, max(0.8, 0.8 + luck * 0.16 + merchant_pity * 0.75 + pressure))


def special_quality_chance_percent(luck: float, loop_tier: int, merchant_pity: float = 0.0) -> float:
    pressure = (loop_tier - 1) * 0.45
    return min(38.0, max(1.0, 1.0 + luck * 0.30 + merchant_pity * 1.15 + pressure))


def rarity_weights(luck: float, enemy_scaling: float, loop_tier: int, merchant_pity: float = 0.0) -> List[Tuple[str, float]]:
    pressure = luck * 0.07 + enemy_scaling * 0.06 + (loop_tier - 1) * 1.25 + merchant_pity * 1.2
    return [
        ("common", max(38.0 - pressure * 2.1, 9.0)),
        ("uncommon", 28.0),
        ("rare", 12.0 + pressure),
        ("mythical", 3.8 + pressure * 0.65),
        ("legendary", 0.8 + pressure * 0.24),
    ]


def quality_weights(luck: float, loop_tier: int, merchant_pity: float = 0.0) -> List[Tuple[str, float]]:
    pressure = luck * 0.06 + (loop_tier - 1) * 0.55 + merchant_pity * 1.2
    return [
        ("trash", max(24.0 - pressure * 1.4, 5.0)),
        ("worn", 27.0),
        ("used", 28.0),
        ("polished", 13.0 + pressure),
        ("new", 5.5 + pressure * 0.85),
    ]


def roll_rarity(
    rng: random.Random,
    luck: float,
    enemy_scaling: float,
    loop_tier: int,
    merchant_pity: float = 0.0,
) -> str:
    if rng.random() * 100 < corrupted_chance_percent(luck, enemy_scaling, loop_tier, merchant_pity):
        return "corrupted"
    return weighted_choice(rng, rarity_weights(luck, enemy_scaling, loop_tier, merchant_pity))


def roll_quality(
    rng: random.Random,
    luck: float,
    loop_tier: int,
    merchant_pity: float = 0.0,
) -> str:
    if rng.random() * 100 < special_quality_chance_percent(luck, loop_tier, merchant_pity):
        return "special craft"
    return weighted_choice(rng, quality_weights(luck, loop_tier, merchant_pity))


def location_ilevel(run: RunState) -> int:
    location = LOCATIONS[run.location_index]
    return location.min_ilevel + (run.loop_tier - 1) * 8


def roll_item(
    rng: random.Random,
    run: RunState,
    luck: float,
    enemy_scaling: float,
    force_rarity: str | None = None,
    force_quality: str | None = None,
    merchant_pity: float = 0.0,
) -> Item:
    slot = rng.choice(EQUIPMENT_SLOTS)
    rarity = force_rarity or roll_rarity(rng, luck, enemy_scaling, run.loop_tier, merchant_pity)
    quality = force_quality or roll_quality(rng, luck, run.loop_tier, merchant_pity)
    ilevel = roll_location_ilevel(rng, run, enemy_scaling)
    set_name = None
    set_candidates = [name for name, definition in SETS.items() if slot in definition.required_slots]
    set_chance = 0.12 + min(0.25, luck / 400) + (0.04 if rarity in {"mythical", "legendary", "corrupted"} else 0)
    if set_candidates and rng.random() < set_chance:
        set_name = rng.choice(set_candidates)

    stat_count = {"common": 1, "uncommon": 2, "rare": 3, "mythical": 4, "legendary": 5, "corrupted": 6}[rarity]
    budget = ilevel * RARITY_MULTIPLIERS[rarity] * QUALITY_MULTIPLIERS[quality]
    if run.loop_tier == 1:
        budget += 1.6 if run.location_index == 0 else 1.0
    stats = {}
    pool = [stat for stat in SLOT_STAT_POOLS[slot] if stat not in PERMANENT_ONLY_STAT_KEYS]
    if len(pool) < stat_count:
        pool.extend(
            stat
            for stat in STAT_KEYS
            if stat not in PERMANENT_ONLY_STAT_KEYS
            and stat not in pool
            and stat not in {"Enemy Scaling%"}
        )
    rng.shuffle(pool)
    for stat in pool[:stat_count]:
        if stat in {"ATK", "HP"}:
            amount = round(budget * (0.8 if stat == "ATK" else 3.8))
        else:
            minimum = 2.0 if run.loop_tier == 1 and run.location_index == 0 else 1.2
            amount = round(max(minimum, budget * rng.uniform(0.22, 0.46)), 1)
        stats[stat] = stats.get(stat, 0.0) + amount

    drawback = ""
    if rarity == "corrupted":
        drawback_candidates = [
            stat for stat in ("HP", "Evasion%", "Coin Acquisition Boost%", "XP Boost%") if stat in stats
        ] or list(stats.keys()) or ["HP"]
        drawback_stat = rng.choice(drawback_candidates)
        penalty = round(max(4, ilevel * 0.35), 1)
        stats[drawback_stat] = stats.get(drawback_stat, 0.0) - penalty
        drawback = f"{drawback_stat} {penalty:g} lower"

    relic_pool = list(RELICS.values())
    if slot == "relic" and relic_pool and rng.random() < 0.28:
        relic = rng.choice(relic_pool)
        prefix = ""
        noun = relic["name"]
    else:
        prefix = rng.choice(RARITY_NAMES[rarity])
        noun = rng.choice(SLOT_NAMES[slot])
    set_prefix = f"{set_name} " if set_name and rng.random() < 0.7 else ""
    name = f"{prefix} {set_prefix}{noun}".replace("  ", " ").strip()
    value = int(max(1, budget * 11 + stat_count * 8))
    item_id = f"{run.seed:x}-{run.loop_tier}-{rng.getrandbits(40):x}"
    return Item(
        id=item_id,
        name=name,
        slot=slot,
        rarity=rarity,
        quality=quality,
        ilevel=ilevel,
        stats=stats,
        set_name=set_name,
        value=value,
        drawback=drawback,
    )


def deterministic_item_value(item: Item, quality: str | None = None) -> int:
    target_quality = quality or item.quality
    rarity_multiplier = RARITY_MULTIPLIERS.get(item.rarity, 1.0)
    quality_multiplier = QUALITY_MULTIPLIERS.get(target_quality, 1.0)
    stat_count = len([amount for stat, amount in item.stats.items() if amount and stat not in PERMANENT_ONLY_STAT_KEYS])
    level_component = max(1, item.ilevel) * 7
    stat_component = max(1, stat_count) * 18
    return max(1, int(round((ITEM_PRICE_BASE + level_component + stat_component) * rarity_multiplier * quality_multiplier)))


def caravan_price(item: Item) -> int:
    return max(8, int(round(deterministic_item_value(item) * CARAVAN_BUY_RATE)))


def sell_value(item: Item) -> int:
    return max(1, int(round(deterministic_item_value(item) * SELL_VALUE_RATE)))


def repair_cost(item: Item) -> int:
    index = QUALITIES.index(item.quality)
    if index >= len(QUALITIES) - 1:
        return 0
    next_quality = QUALITIES[index + 1]
    return max(5, int(round(deterministic_item_value(item, next_quality) * IMPROVEMENT_RATE)))


def improve_quality(item: Item, locked_stats: list[str] | None = None) -> bool:
    index = QUALITIES.index(item.quality)
    if index >= len(QUALITIES) - 1:
        return False
    locked = set(locked_stats or [])
    old_multiplier = QUALITY_MULTIPLIERS[item.quality]
    item.quality = QUALITIES[index + 1]
    new_multiplier = QUALITY_MULTIPLIERS[item.quality]
    ratio = new_multiplier / old_multiplier
    item.value = deterministic_item_value(item)
    for stat in list(item.stats):
        if stat in locked:
            continue
        item.stats[stat] = round(item.stats[stat] * ratio, 1)
    return True
