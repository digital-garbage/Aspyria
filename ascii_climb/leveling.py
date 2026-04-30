from __future__ import annotations

import random

from ascii_climb.content import LEVEL_REWARDS, PERKS
from ascii_climb.models import RunState, format_stat_bonus
from ascii_climb.relics import apply_passive_relics, has_relic_effect
from ascii_climb.state import blocked_positive_amount, is_stat_locked, is_valid_stat, safe_apply_buff


def queue_level_rewards(run: RunState, levels_gained: list[int], boss_defeated: bool = False) -> None:
    for level in levels_gained:
        reward_type = "perk" if level % 5 == 0 else "stat"
        run.pending_level_rewards.append({"type": reward_type, "source": f"level {level}", "level": level})
    if boss_defeated:
        run.pending_level_rewards.append({"type": "perk", "source": "boss", "level": run.level})


def generate_level_reward_options(rng: random.Random, run: RunState, reward: dict) -> list[dict]:
    apply_passive_relics(run)
    pool = PERKS if reward.get("type") == "perk" else LEVEL_REWARDS
    options = list(pool.values())
    if reward.get("type") == "perk" and has_relic_effect(run, "boss_perk_improvement") and reward.get("source") == "boss":
        options = [dict(option, amount_multiplier=1.25) for option in options]
    if reward.get("type") == "stat" and run.favored_stat:
        favored = [option for option in options if option.get("stat") == run.favored_stat]
        if favored and rng.random() < 0.45:
            options = favored + options
    rng.shuffle(options)
    count = 3 + run.extra_level_options
    return [dict(option) for option in options[:count]]


def apply_level_reward(run: RunState, reward: dict) -> str:
    reward_type = reward_kind(reward)
    title = reward.get("title", "Reward")
    multiplier = float(reward.get("amount_multiplier", 1.0))
    if reward_type == "stat":
        stat = reward.get("stat")
        raw_amount = float(reward.get("amount", 0.0)) * run.level_reward_multiplier * multiplier
        amount = blocked_positive_amount(run, stat, raw_amount)
        if not is_valid_stat(stat):
            return f"{title} fizzles; the reward points at an unknown stat."
        if stat in run.run_debuffs:
            return f"{title} could not boost cursed {stat}."
        safe_apply_buff(run, stat, amount)
        return f"{title}: {format_stat_bonus(stat, amount)}."
    effect = reward.get("effect")
    params = reward.get("params", {})
    if effect == "post_fight_heal_bonus":
        run.post_fight_heal_bonus += float(params.get("heal_bonus", 0.0)) * multiplier
    elif effect == "loot_bonus":
        run.loot_bonus_chance += float(params.get("chance", 0.0)) * multiplier
    elif effect == "bonus_coins":
        run.coins += int(float(params.get("coins", 0)) * multiplier)
    elif effect == "extra_level_option":
        if run.extra_level_options_chosen >= 2:
            run.chosen_perks.append(str(reward.get("id", title)))
            return "Perk skipped: +1 choice is already capped at two applications this run."
        gained = int(params.get("extra_options", 1))
        remaining = max(0, 2 - run.extra_level_options_chosen)
        applied = min(gained, remaining)
        run.extra_level_options += applied
        run.extra_level_options_chosen += applied
    elif effect == "flee_protection":
        run.relic_charges_used["perk_flee_protection"] = -int(params.get("charges", 1))
    run.chosen_perks.append(str(reward.get("id", title)))
    return f"Perk gained: {describe_level_reward(reward)}."


def describe_level_reward(reward: dict) -> str:
    return describe_level_reward_for_run(None, reward)


def describe_level_reward_for_run(run: RunState | None, reward: dict) -> str:
    title = reward.get("title", "Reward")
    multiplier = float(reward.get("amount_multiplier", 1.0))
    if reward_kind(reward) == "stat":
        stat = reward.get("stat", "")
        raw_amount = float(reward.get("amount", 0.0)) * multiplier
        amount = blocked_positive_amount(run, stat, raw_amount) if run is not None else raw_amount
        text = f"{title}: {format_stat_bonus(stat, amount)}".strip()
        if run is not None and is_stat_locked(run, stat):
            text += " [LOCKED]"
        return text
    effect = reward.get("effect", "")
    params = reward.get("params", {})
    if effect == "post_fight_heal_bonus":
        return f"{title}: heal +{float(params.get('heal_bonus', 0.0)) * multiplier * 100:g}% of max HP after every fight"
    if effect == "loot_bonus":
        return f"{title}: loot drop chance +{float(params.get('chance', 0.0)) * multiplier * 100:g}%"
    if effect == "bonus_coins":
        return f"{title}: gain {int(float(params.get('coins', 0)) * multiplier)} coins immediately"
    if effect == "extra_level_option":
        return f"{title}: see +{int(params.get('extra_options', 1))} extra option on future level rewards"
    if effect == "flee_protection":
        return f"{title}: {int(params.get('charges', 1))} flee penalty protection charge"
    return title


def reward_kind(reward: dict) -> str:
    if reward.get("type"):
        return str(reward["type"])
    if reward.get("effect"):
        return "perk"
    return "stat"
