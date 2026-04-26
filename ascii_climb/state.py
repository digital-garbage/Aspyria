from __future__ import annotations

from typing import Any

from ascii_climb.models import Item, RunState, STAT_KEYS


VALID_STATS = set(STAT_KEYS) | {"Damage Reduction%", "Damage Taken%", "Gold Payout%"}


def is_valid_stat(stat: Any) -> bool:
    return isinstance(stat, str) and stat in VALID_STATS


def sanitize_stat_map(values: dict | None) -> dict[str, float]:
    if not values:
        return {}
    cleaned = {}
    for key, value in values.items():
        if is_valid_stat(key):
            cleaned[key] = float(value)
    return cleaned


def sanitize_run_state(run: RunState | None) -> None:
    if run is None:
        return
    run.run_buffs = sanitize_stat_map(run.run_buffs)
    run.run_debuffs = sanitize_stat_map(run.run_debuffs)
    run.locked_stats = [stat for stat in run.locked_stats if is_valid_stat(stat)]
    cleaned_modifiers = []
    for modifier in run.timed_stat_modifiers:
        stat = modifier.get("stat")
        if not is_valid_stat(stat):
            continue
        cleaned_modifiers.append(
            {
                "stat": stat,
                "multiplier": float(modifier.get("multiplier", 1.0)),
                "remaining_fights": max(0, int(modifier.get("remaining_fights", 0))),
                "label": str(modifier.get("label", "")),
            }
        )
    run.timed_stat_modifiers = [modifier for modifier in cleaned_modifiers if modifier["remaining_fights"] > 0]
    if run.random_gear_offer:
        try:
            run.random_gear_offer = Item.from_dict(run.random_gear_offer).to_dict()
        except (KeyError, TypeError, ValueError):
            run.random_gear_offer = None
            run.random_gear_offer_cost = 0
    if run.active_fight:
        run.active_fight = sanitize_active_fight(run.active_fight)


def sanitize_active_fight(fight: dict | None) -> dict | None:
    if not fight:
        return None
    try:
        enemy_name = str(fight["enemy_name"])
        enemy_max_hp = max(1, int(fight["enemy_max_hp"]))
        enemy_hp = max(1, min(enemy_max_hp, int(fight["enemy_hp"])))
        enemy_atk = max(1, int(fight["enemy_atk"]))
        xp = max(1, int(fight["xp"]))
        coins = max(1, int(fight["coins"]))
        seed = int(fight.get("seed", 0))
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "enemy_name": enemy_name,
        "enemy_hp": enemy_hp,
        "enemy_max_hp": enemy_max_hp,
        "enemy_atk": enemy_atk,
        "xp": xp,
        "coins": coins,
        "boss": bool(fight.get("boss", False)),
        "seed": seed,
    }


def safe_apply_buff(run: RunState, stat: str | None, amount: float) -> bool:
    if not is_valid_stat(stat):
        return False
    if is_stat_locked(run, stat):
        return False
    run.run_buffs[stat] = max(0.0, run.run_buffs.get(stat, 0.0) + float(amount))
    return True


def safe_apply_debuff(run: RunState, stat: str | None, amount: float, current_value: float | None = None) -> bool:
    if not is_valid_stat(stat):
        return False
    amount = max(0.0, float(amount))
    if current_value is not None:
        amount = min(amount, max(0.0, float(current_value) - minimum_stat_value(stat)))
    if amount <= 0:
        return False
    run.run_debuffs[stat] = max(0.0, run.run_debuffs.get(stat, 0.0) + amount)
    return True


def is_stat_locked(run: RunState, stat: str | None) -> bool:
    return isinstance(stat, str) and stat in run.locked_stats


def lock_stat(run: RunState, stat: str | None) -> bool:
    if not is_valid_stat(stat) or is_stat_locked(run, stat):
        return False
    run.locked_stats.append(stat)
    run.locked_stats.sort()
    return True


def blocked_positive_amount(run: RunState, stat: str | None, amount: float) -> float:
    if not is_valid_stat(stat):
        return 0.0
    return 0.0 if is_stat_locked(run, stat) else float(amount)


def minimum_stat_value(stat: str) -> float:
    return 1.0 if stat in {"ATK", "HP"} else 0.0


def clamp_effective_stats(stats: dict[str, float]) -> dict[str, float]:
    for stat in list(stats):
        stats[stat] = max(minimum_stat_value(stat), float(stats.get(stat, 0.0)))
    stats["CR%"] = min(stats.get("CR%", 0.0), 95.0)
    stats["Evasion%"] = min(stats.get("Evasion%", 0.0), 80.0)
    stats["Multi-Attack Chance%"] = min(stats.get("Multi-Attack Chance%", 0.0), 85.0)
    stats["Megacrit Chance%"] = min(stats.get("Megacrit Chance%", 0.0), 50.0)
    return stats


def decay_timed_modifiers(run: RunState) -> None:
    active = []
    for modifier in run.timed_stat_modifiers:
        remaining = int(modifier.get("remaining_fights", 0)) - 1
        if remaining > 0 and is_valid_stat(modifier.get("stat")):
            updated = dict(modifier)
            updated["remaining_fights"] = remaining
            active.append(updated)
    run.timed_stat_modifiers = active
