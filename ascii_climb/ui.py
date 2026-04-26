from __future__ import annotations

from typing import Iterable, List

from ascii_climb.content import LOCATIONS
from ascii_climb.meta import effective_stats, set_bonuses, upgrade_cost
from ascii_climb.models import Item, MetaState, RunState, STAT_KEYS


def line(width: int = 78) -> str:
    return "+" + "-" * (width - 2) + "+"


def panel(title: str, rows: Iterable[str], width: int = 78) -> str:
    output = [line(width), f"| {title[: width - 4].ljust(width - 4)} |", line(width)]
    for row in rows:
        text = row[: width - 4]
        output.append(f"| {text.ljust(width - 4)} |")
    output.append(line(width))
    return "\n".join(output)


def ask(prompt: str, valid: set[str] | None = None) -> str:
    while True:
        try:
            answer = input(prompt).strip().lower()
        except EOFError:
            if valid:
                if "4" in valid:
                    return "4"
                return sorted(valid)[-1]
            return ""
        if valid is None or answer in valid:
            return answer
        print(f"Choose one of: {', '.join(sorted(valid))}")


def print_logs(logs: List[str], limit: int = 12) -> None:
    shown = logs[-limit:]
    print(panel("Combat Log", shown))


def format_stats(stats: dict) -> List[str]:
    rows = []
    for stat in STAT_KEYS:
        value = stats.get(stat, 0.0)
        suffix = "" if stat in {"ATK", "HP"} else "%"
        rows.append(f"{stat}: {value:.1f}{suffix}")
    if stats.get("Damage Reduction%"):
        rows.append(f"Damage Reduction%: {stats['Damage Reduction%']:.1f}%")
    if stats.get("Damage Taken%"):
        rows.append(f"Damage Taken%: {stats['Damage Taken%']:.1f}%")
    if stats.get("Gold Payout%"):
        rows.append(f"Gold Payout%: {stats['Gold Payout%']:.1f}%")
    return rows


def show_character(meta: MetaState, run: RunState) -> None:
    location = LOCATIONS[run.location_index]
    stats = effective_stats(meta, run)
    rows = [
        f"Location: {location.name} | Loop tier {run.loop_tier} | Fight {run.fights_in_location}/{location.fights_to_boss}",
        f"HP: {run.current_hp}/{int(stats['HP'])} | Level: {run.level} | XP: {run.xp}/{run.level * 100}",
        f"Coins: {run.coins} | Defeats: {run.defeats}/4 | Bosses defeated: {run.completed_bosses}",
        f"Inventory: {len(run.inventory)}/{meta.inventory_capacity()}",
    ]
    print(panel("Run", rows))
    print(panel("Stats", format_stats(stats)))
    active_sets = []
    bonuses = set_bonuses(run)
    if bonuses:
        active_sets = [f"{stat}: +{amount:g}" for stat, amount in bonuses.items()]
    print(panel("Set Bonuses", active_sets or ["No active set bonuses."]))
    run_buffs = [f"{stat}: {amount:+g}" for stat, amount in run.run_buffs.items() if amount]
    print(panel("Run Enhancements", run_buffs or ["No temporary run enhancements yet."]))


def item_rows(items: List[Item]) -> List[str]:
    if not items:
        return ["Empty."]
    rows = []
    for index, item in enumerate(items, 1):
        rows.append(f"{index}. {item.label()} | value {item.value}")
        rows.append(f"   {item.stat_line()}")
    return rows


def choose_item(items: List[Item], prompt: str = "Item number: ") -> Item | None:
    if not items:
        print("No items.")
        return None
    print(panel("Items", item_rows(items)))
    answer = ask(prompt)
    if not answer.isdigit():
        return None
    index = int(answer) - 1
    if index < 0 or index >= len(items):
        return None
    return items[index]


def show_equipment(run: RunState) -> None:
    rows = []
    for slot, item in run.equipment.items():
        rows.append(f"{slot}: {item.label() if item else '-'}")
        if item:
            rows.append(f"   {item.stat_line()}")
    print(panel("Equipment", rows))


def show_meta(meta: MetaState) -> None:
    rows = [f"Gold: {meta.gold}", f"Inventory capacity: {meta.inventory_capacity()}"]
    for stat in STAT_KEYS:
        current = meta.upgrades.get(stat, 0)
        next_cost = "MAX" if current >= 50 else str(upgrade_cost(stat, current + 1))
        rows.append(f"{stat}: level {current}/50 | next {next_cost} gold")
    print(panel("Permanent Upgrades", rows))
