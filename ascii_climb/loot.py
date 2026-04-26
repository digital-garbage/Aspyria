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
from ascii_climb.models import EQUIPMENT_SLOTS, QUALITIES, RARITIES, Item, RunState


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
    pressure = enemy_scaling * 0.05 + (loop_tier - 1) * 0.75
    return min(35.0, max(1.0, 1.0 + luck * 0.25 + merchant_pity + pressure))


def special_quality_chance_percent(luck: float, loop_tier: int, merchant_pity: float = 0.0) -> float:
    pressure = (loop_tier - 1) * 0.5
    return min(35.0, max(1.0, 1.0 + luck * 0.25 + merchant_pity + pressure))


def rarity_weights(luck: float, enemy_scaling: float, loop_tier: int, merchant_pity: float = 0.0) -> List[Tuple[str, float]]:
    pressure = luck * 0.04 + enemy_scaling * 0.08 + (loop_tier - 1) * 1.5 + merchant_pity
    return [
        ("common", max(35.0 - pressure * 2.2, 8.0)),
        ("uncommon", 26.0),
        ("rare", 14.0 + pressure),
        ("mythical", 5.0 + pressure * 0.55),
        ("legendary", 1.2 + pressure * 0.18),
    ]


def quality_weights(luck: float, loop_tier: int, merchant_pity: float = 0.0) -> List[Tuple[str, float]]:
    pressure = luck * 0.03 + (loop_tier - 1) * 0.6 + merchant_pity
    return [
        ("trash", max(22.0 - pressure, 4.0)),
        ("worn", 25.0),
        ("used", 26.0),
        ("polished", 15.0 + pressure),
        ("new", 8.0 + pressure * 0.7),
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

    stat_count = {"common": 1, "uncommon": 2, "rare": 2, "mythical": 3, "legendary": 4, "corrupted": 4}[rarity]
    budget = ilevel * RARITY_MULTIPLIERS[rarity] * QUALITY_MULTIPLIERS[quality]
    if run.loop_tier == 1:
        budget += 1.6 if run.location_index == 0 else 1.0
    stats = {}
    pool = SLOT_STAT_POOLS[slot][:]
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
        drawback_stat = rng.choice(["HP", "Evasion%", "Coin Acquisition Boost%", "XP Boost%"])
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


def sell_value(item: Item) -> int:
    return max(1, item.value // 3)


def repair_cost(item: Item) -> int:
    index = QUALITIES.index(item.quality)
    if index >= len(QUALITIES) - 1:
        return 0
    return max(5, int(item.value * 0.22 * (index + 1)))


def improve_quality(item: Item) -> bool:
    index = QUALITIES.index(item.quality)
    if index >= len(QUALITIES) - 1:
        return False
    old_multiplier = QUALITY_MULTIPLIERS[item.quality]
    item.quality = QUALITIES[index + 1]
    new_multiplier = QUALITY_MULTIPLIERS[item.quality]
    ratio = new_multiplier / old_multiplier
    item.value = int(item.value * ratio)
    for stat in list(item.stats):
        item.stats[stat] = round(item.stats[stat] * ratio, 1)
    return True
