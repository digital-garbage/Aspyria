from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List

from ascii_climb.models import RunState, STAT_KEYS, format_stat_bonus, stat_label
from ascii_climb.state import blocked_positive_amount, is_stat_locked, minimum_stat_value, safe_apply_buff, safe_apply_debuff


@dataclass(frozen=True)
class EnhancementOption:
    title: str
    buffs: Dict[str, float]
    penalties: Dict[str, float]
    rarity: str = "common"

    def describe(self) -> str:
        return describe_enhancement(self)


def describe_enhancement(option: EnhancementOption, run: RunState | None = None) -> str:
        parts = []
        for stat, amount in option.buffs.items():
            shown = blocked_positive_amount(run, stat, amount) if run is not None else amount
            label = format_stat_bonus(stat, shown)
            if run is not None and is_stat_locked(run, stat):
                label += " [LOCKED]"
            parts.append(label)
        for stat, amount in option.penalties.items():
            suffix = "" if stat in {"ATK", "HP"} else "%"
            parts.append(f"{stat_label(stat)}: -{amount:g}{suffix}")
        return ", ".join(parts)


MOB_BUFF_STATS = [
    "ATK",
    "HP",
    "CR%",
    "CD%",
    "Luck%",
    "Evasion%",
    "Multi-Attack Chance%",
    "Megacrit Chance%",
    "Megacrit Damage%",
    "XP Boost%",
    "Coin Acquisition Boost%",
]


def _eligible_stats(run: RunState, stats: List[str]) -> List[str]:
    return [stat for stat in stats if stat not in run.run_debuffs]


def _run_luck_hint(run: RunState) -> float:
    equipped_luck = sum(item.stats.get("Luck%", 0.0) for item in run.equipped_items())
    return max(0.0, run.run_buffs.get("Luck%", 0.0) + equipped_luck)


def generate_stage_enhancements(rng: random.Random, run: RunState) -> List[EnhancementOption]:
    stats = _eligible_stats(run, MOB_BUFF_STATS)
    rng.shuffle(stats)
    options = []
    luck = min(120.0, _run_luck_hint(run))
    rarity_weights = [
        max(42.0, 78.0 - luck * 0.30),
        18.0 + luck * 0.16,
        4.0 + luck * 0.14,
    ]
    for stat in stats[:3]:
        amount = 4.0 if stat in {"ATK", "HP"} else 2.0
        if stat in {"Megacrit Damage%", "CD%"}:
            amount = 5.0
        rarity = rng.choices(["common", "uncommon", "rare"], weights=rarity_weights, k=1)[0]
        if rarity == "uncommon":
            amount *= 1.35
        elif rarity == "rare":
            amount *= 2.0
        options.append(
            EnhancementOption(
                title=stat_label(stat),
                buffs={stat: amount},
                penalties={},
                rarity=rarity,
            )
        )
    return options


def generate_wishing_well_options(
    rng: random.Random, run: RunState, current_stats: dict | None = None
) -> List[EnhancementOption]:
    stats = _eligible_stats(run, MOB_BUFF_STATS + ["Enemy Scaling%"])
    rng.shuffle(stats)
    options = []
    for main in stats[:3]:
        penalty_pool = [stat for stat in MOB_BUFF_STATS if stat != main]
        if current_stats:
            penalty_pool = [
                stat
                for stat in penalty_pool
                if current_stats.get(stat, minimum_stat_value(stat)) > minimum_stat_value(stat) + (12.0 if stat not in {"ATK", "HP"} else 18.0)
            ]
        rng.shuffle(penalty_pool)
        penalties = {}
        for stat in penalty_pool[:3]:
            penalties[stat] = 12.0 if stat not in {"ATK", "HP"} else 18.0
        if len(penalties) < 3:
            continue
        buff = 38.0 if main in {"ATK", "HP"} else 24.0
        if main in {"Megacrit Damage%", "CD%"}:
            buff = 56.0
        options.append(
            EnhancementOption(
                title=f"Ask for {stat_label(main)}",
                buffs={main: buff},
                penalties=penalties,
                rarity="mythical",
            )
        )
    return options


def apply_enhancement(run: RunState, option: EnhancementOption) -> str:
    blocked = []
    for stat, amount in option.buffs.items():
        if stat in run.run_debuffs:
            blocked.append(stat)
            continue
        safe_apply_buff(run, stat, amount)
    for stat, amount in option.penalties.items():
        safe_apply_debuff(run, stat, amount)
    if blocked:
        return f"Applied {option.title}, but cursed stats could not be boosted: {', '.join(blocked)}."
    return f"Applied {option.title}: {describe_enhancement(option, run)}."
