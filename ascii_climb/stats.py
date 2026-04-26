from __future__ import annotations

import time

from ascii_climb.combat import CombatResult
from ascii_climb.models import Item, ItemCollectionRecord, LifetimeStats, RunRecord, RunState

RARITY_RANK = {
    "common": 1,
    "uncommon": 2,
    "rare": 3,
    "mythical": 4,
    "legendary": 5,
    "corrupted": 6,
}


def start_run_timer(run: RunState, now: float | None = None) -> None:
    run.started_at = now if now is not None else time.time()
    run.first_loop_clear_recorded = False


def record_combat_result(stats: LifetimeStats, result: CombatResult, run: RunState, now: float | None = None) -> None:
    if not result.victory:
        if not run.active:
            record_failed_run(stats, run, now)
        return
    enemy_name = result.enemy.name
    stats.enemies_defeated += 1
    stats.enemy_counts[enemy_name] = stats.enemy_counts.get(enemy_name, 0) + 1
    if result.enemy.boss:
        stats.bosses_defeated += 1
        stats.boss_counts[enemy_name] = stats.boss_counts.get(enemy_name, 0) + 1
    if run.loop_tier >= 2 and not run.first_loop_clear_recorded:
        record_successful_run(stats, run, now)
        run.first_loop_clear_recorded = True


def record_item_collected(stats: LifetimeStats, item: Item) -> None:
    record = stats.item_codex.get(item.name)
    if record is None:
        record = ItemCollectionRecord(name=item.name)
        stats.item_codex[item.name] = record
    record.count += 1
    record.highest_value = max(record.highest_value, item.value)
    if RARITY_RANK.get(item.rarity, 0) >= RARITY_RANK.get(record.highest_rarity, 0):
        record.highest_rarity = item.rarity
    _bump(record.slots, item.slot)
    _bump(record.rarities, item.rarity)
    _bump(record.qualities, item.quality)
    if item.set_name:
        _bump(record.sets, item.set_name)
    _record_rare_item(stats, item)


def record_failed_run(stats: LifetimeStats, run: RunState, now: float | None = None) -> None:
    if run.loop_tier >= 2 or run.first_loop_clear_recorded:
        return
    record = _run_record(run, now)
    if stats.quickest_failed_run is None or record.duration_seconds < stats.quickest_failed_run.duration_seconds:
        stats.quickest_failed_run = record
    if stats.longest_failed_run is None or record.duration_seconds > stats.longest_failed_run.duration_seconds:
        stats.longest_failed_run = record


def record_successful_run(stats: LifetimeStats, run: RunState, now: float | None = None) -> None:
    record = _run_record(run, now)
    if stats.quickest_successful_run is None or record.duration_seconds < stats.quickest_successful_run.duration_seconds:
        stats.quickest_successful_run = record
    if stats.longest_successful_run is None or record.duration_seconds > stats.longest_successful_run.duration_seconds:
        stats.longest_successful_run = record


def add_play_time(stats: LifetimeStats, seconds: float) -> None:
    if seconds > 0:
        stats.play_time_seconds += seconds


def _run_record(run: RunState, now: float | None = None) -> RunRecord:
    ended_at = now if now is not None else time.time()
    started_at = run.started_at or ended_at
    return RunRecord(
        duration_seconds=max(0.0, ended_at - started_at),
        seed=run.seed,
        loop_tier=run.loop_tier,
        completed_bosses=run.completed_bosses,
        ended_at=ended_at,
    )


def _record_rare_item(stats: LifetimeStats, item: Item) -> None:
    entry = {
        "name": item.name,
        "rarity": item.rarity,
        "quality": item.quality,
        "slot": item.slot,
        "value": item.value,
        "set_name": item.set_name or "",
    }
    stats.rarest_items.append(entry)
    stats.rarest_items.sort(
        key=lambda row: (RARITY_RANK.get(row.get("rarity", ""), 0), int(row.get("value", 0))),
        reverse=True,
    )
    del stats.rarest_items[20:]


def _bump(mapping: dict[str, int], key: str) -> None:
    mapping[key] = mapping.get(key, 0) + 1
