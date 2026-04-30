from __future__ import annotations

from ascii_climb.content import RELICS
from ascii_climb.models import RunState


def equipped_relic_effects(run: RunState) -> list[dict]:
    relic = run.equipment.get("relic")
    if relic is None:
        return []
    effects = []
    for data in RELICS.values():
        if data.get("name") == relic.name:
            effects.append(data)
    return effects


def has_relic_effect(run: RunState, effect_id: str) -> bool:
    return any(effect.get("effect_id") == effect_id for effect in equipped_relic_effects(run))


def relic_param(run: RunState, effect_id: str, key: str, default=0):
    for effect in equipped_relic_effects(run):
        if effect.get("effect_id") == effect_id:
            return effect.get("params", {}).get(key, default)
    return default


def consume_relic_charge(run: RunState, effect_id: str) -> bool:
    for effect in equipped_relic_effects(run):
        if effect.get("effect_id") != effect_id:
            continue
        charges = int(effect.get("params", {}).get("charges", 0))
        used = run.relic_charges_used.get(effect_id, 0)
        if charges <= 0 or used < charges:
            run.relic_charges_used[effect_id] = used + 1
            return True
    return False


def apply_passive_relics(run: RunState) -> None:
    multiplier = 1.0
    extra_options = 0
    base_extra_options = min(2, max(run.extra_level_options, run.extra_level_options_chosen))
    loot_bonus = 0.0
    heal_bonus = 0.0
    for relic in equipped_relic_effects(run):
        effect_id = relic.get("effect_id")
        params = relic.get("params", {})
        if effect_id == "level_reward_multiplier":
            multiplier = max(multiplier, float(params.get("multiplier", 1.0)))
        elif effect_id == "extra_level_option":
            extra_options += int(params.get("extra_options", 0))
        elif effect_id == "necromancer_loot_bonus":
            loot_bonus += float(params.get("chance", 0.0))
        elif effect_id == "post_fight_heal_bonus":
            heal_bonus += float(params.get("heal_bonus", 0.0))
    run.level_reward_multiplier = multiplier
    run.extra_level_options = min(2, base_extra_options + extra_options)
    run.loot_bonus_chance = loot_bonus
    run.post_fight_heal_bonus = heal_bonus
