from __future__ import annotations

import random

from ascii_climb.content import LOCATIONS
from ascii_climb.models import RunState


def current_ilevel_range(run: RunState, enemy_scaling: float) -> tuple[int, int]:
    location = LOCATIONS[run.location_index]
    loop_bonus = max(0, run.loop_tier - 1) * 8
    scaling_bonus = int(max(0.0, enemy_scaling) // 8)
    minimum = location.min_ilevel + loop_bonus + scaling_bonus
    maximum = location.max_ilevel + loop_bonus + scaling_bonus * 2
    return max(1, minimum), max(minimum, maximum)


def roll_location_ilevel(rng: random.Random, run: RunState, enemy_scaling: float) -> int:
    minimum, maximum = current_ilevel_range(run, enemy_scaling)
    return rng.randint(minimum, maximum)


def gear_advantage_bonuses(run: RunState) -> dict[str, float]:
    location = LOCATIONS[run.location_index]
    surplus = max(0.0, run.average_ilevel() - location.min_ilevel)
    if surplus <= 0:
        return {}
    steps = min(8, int(surplus // 2) + 1)
    return {
        "ATK": steps * 1.5,
        "HP": steps * 4.0,
        "Evasion%": steps * 0.8,
        "Luck%": steps * 0.8,
    }
