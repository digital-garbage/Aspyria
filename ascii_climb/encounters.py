from __future__ import annotations

import random
from dataclasses import dataclass, field

from ascii_climb.content import ENCOUNTERS
from ascii_climb.loot import roll_item, roll_rarity
from ascii_climb.meta import effective_stats
from ascii_climb.models import Item, MetaState, QUALITIES, RANDOM_RUN_STAT_KEYS, RunState, STAT_KEYS
from ascii_climb.progression import apply_enhancement, describe_enhancement, generate_wishing_well_options
from ascii_climb.state import blocked_positive_amount, safe_apply_buff, safe_apply_debuff


@dataclass
class EncounterResult:
    title: str
    logs: list[str] = field(default_factory=list)
    loot: Item | None = None
    choices: list[dict] = field(default_factory=list)
    event: dict | None = None


def attempt_random_encounter(
    rng: random.Random,
    meta: MetaState,
    run: RunState,
    trigger: str = "post_fight",
) -> EncounterResult | None:
    return random_event(rng, meta, run, trigger=trigger)


def random_event(
    rng: random.Random,
    meta: MetaState,
    run: RunState,
    trigger: str = "post_fight",
    event: dict | None = None,
    choice_index: int = 0,
    preview: bool = False,
) -> EncounterResult | None:
    stats = effective_stats(meta, run)
    if event is None:
        chance = min(0.20, 0.08 + min(stats.get("Luck%", 0.0) * 0.0005, 0.12))
        if rng.random() >= chance:
            return None
        candidates = [
            encounter
            for encounter in ENCOUNTERS.values()
            if encounter.get("trigger", "post_fight") == trigger
            and rng.random() < float(encounter.get("chance", 1.0))
        ]
        if not candidates:
            return None
        event = _weighted_choice(rng, candidates)
    result = EncounterResult(
        title=str(event.get("title", "Encounter")),
        choices=list(event.get("choices", [])),
        event=event,
    )
    body = event.get("body") or event.get("text")
    if isinstance(body, list):
        body = rng.choice(body) if body else ""
    if body:
        result.logs.append(str(body))
    if event.get("handler") == "wishing_well" and preview:
        options = generate_wishing_well_options(rng, run, stats)
        event = dict(event, _options=options)
        result.event = event
        result.choices = [
            {"id": str(index), "label": f"{option.title}: {describe_enhancement(option, run)}"}
            for index, option in enumerate(options)
        ]
    if preview:
        return result
    handler = event.get("handler")
    if handler:
        _apply_handler(rng, meta, run, event, result, choice_index)
    else:
        for effect in event.get("effects", []):
            _apply_effect(rng, meta, run, effect, result, choice_index)
    return result


def apply_encounter(
    rng: random.Random,
    meta: MetaState,
    run: RunState,
    encounter: dict,
    choice_index: int = 0,
) -> EncounterResult:
    result = EncounterResult(title=encounter.get("title", "Encounter"))
    for effect in encounter.get("effects", []):
        _apply_effect(rng, meta, run, effect, result, choice_index)
    return result


def _apply_effect(
    rng: random.Random,
    meta: MetaState,
    run: RunState,
    effect: dict,
    result: EncounterResult,
    choice_index: int,
) -> None:
    effect_type = effect.get("type", "message")
    if effect_type == "message":
        result.logs.append(effect.get("text", "Something happens."))
    elif effect_type == "reward_coins":
        amount = int(effect.get("amount", 0))
        run.coins += amount
        result.logs.append(f"+{amount} coins.")
    elif effect_type == "reward_gold":
        amount = int(effect.get("amount", 0))
        meta.gold += amount
        result.logs.append(f"+{amount} gold.")
    elif effect_type == "reward_item":
        stats = effective_stats(meta, run)
        result.loot = roll_item(
            rng,
            run,
            stats.get("Luck%", 0.0),
            stats.get("Enemy Scaling%", 0.0),
            force_rarity=effect.get("rarity"),
            force_quality=effect.get("quality"),
        )
        result.logs.append(f"Found {result.loot.label()}.")
    elif effect_type == "stat_buff":
        stat = effect.get("stat")
        amount = float(effect.get("amount", 0))
        if safe_apply_buff(run, stat, amount):
            result.logs.append(f"{stat} +{amount:g}.")
    elif effect_type == "stat_debuff":
        stat = effect.get("stat")
        amount = float(effect.get("amount", 0))
        if safe_apply_debuff(run, stat, amount, effective_stats(meta, run).get(stat or "", 0.0)):
            result.logs.append(f"{stat} -{amount:g}.")
    elif effect_type == "choice_list":
        choices = effect.get("choices", [])
        if not choices:
            return
        selected = choices[min(choice_index, len(choices) - 1)]
        result.logs.append(selected.get("label", "Choice"))
        for nested in selected.get("effects", []):
            _apply_effect(rng, meta, run, nested, result, choice_index)
    elif effect_type == "shop":
        result.logs.append("A shop offer appears.")
    elif effect_type == "scout":
        result.logs.append("The road ahead feels easier to read.")
    elif effect_type == "crafting":
        result.logs.append("A rough crafting table waits nearby.")
    elif effect_type == "combat":
        result.logs.append(effect.get("text", "Something hostile is close."))


def _apply_handler(
    rng: random.Random,
    meta: MetaState,
    run: RunState,
    event: dict,
    result: EncounterResult,
    choice_index: int,
) -> None:
    handler = event.get("handler")
    params = event.get("params", {})
    stats = effective_stats(meta, run)
    choices = event.get("choices", [])
    choice = choices[min(choice_index, len(choices) - 1)] if choices else {}
    choice_id = choice.get("id", "")
    if choice:
        result.logs.append(str(choice.get("label", "Choice")))

    if handler == "ancient_restore":
        rarity = roll_rarity(rng, stats.get("Luck%", 0.0), stats.get("Enemy Scaling%", 0.0), run.loop_tier)
        if choice_id == "refuse":
            item = roll_item(rng, run, stats.get("Luck%", 0.0), stats.get("Enemy Scaling%", 0.0), force_rarity=rarity, force_quality="worn")
            result.logs.append(f"You keep the ancient {item.name} as-is.")
        else:
            difficulty = {"common": 0, "uncommon": 8, "rare": 18, "mythical": 32, "legendary": 48, "corrupted": 60}[rarity]
            success = rng.random() * 100 < max(5.0, min(90.0, 48.0 + stats.get("Luck%", 0.0) - difficulty))
            quality = "used" if success else "trash"
            item = roll_item(rng, run, stats.get("Luck%", 0.0), stats.get("Enemy Scaling%", 0.0), force_rarity=rarity, force_quality=quality)
            result.logs.append("The restoration holds." if success else "The restoration fails, but something remains.")
        result.loot = item
        result.logs.append(f"Found {item.label()}.")
    elif handler == "bandit_toll":
        if choice_id == "pay":
            loss = int(run.coins * float(params.get("toll_fraction", 0.9)))
            run.coins -= loss
            result.logs.append(f"You pay {loss} coins and the bandit lets you pass.")
        else:
            win_chance = min(0.9, 0.45 + stats.get("ATK", 0.0) / 220 + stats.get("Evasion%", 0.0) / 300)
            if rng.random() < win_chance:
                result.logs.append("You beat the bandit back into the brush.")
                if rng.random() < float(params.get("legendary_chance", 0.25)):
                    result.loot = roll_item(rng, run, stats.get("Luck%", 0.0), stats.get("Enemy Scaling%", 0.0), force_rarity="legendary")
                    result.logs.append(f"The bandit drops {result.loot.label()}.")
            else:
                loss = int(run.coins * 0.35)
                hp_loss = max(1, int(stats.get("HP", 1.0) * 0.18))
                run.coins = max(0, run.coins - loss)
                run.current_hp = max(1, run.current_hp - hp_loss)
                result.logs.append(f"The bandit wounds you for {hp_loss} HP and steals {loss} coins.")
    elif handler == "pitfall":
        stat = rng.choice(RANDOM_RUN_STAT_KEYS)
        run.timed_stat_modifiers.append(
            {
                "stat": stat,
                "multiplier": float(params.get("multiplier", 0.5)),
                "remaining_fights": int(params.get("fights", 3)),
                "label": result.title,
            }
        )
        result.logs.append(f"{stat} is halved for the next 3 fights.")
    elif handler == "old_monk":
        stat = rng.choice(RANDOM_RUN_STAT_KEYS)
        amount = blocked_positive_amount(
            run,
            stat,
            10.0 if stat in {"ATK", "HP"} else max(1.0, stats.get(stat, 0.0) * 0.10),
        )
        safe_apply_buff(run, stat, amount)
        luck_amount = blocked_positive_amount(run, "Luck%", 5.0)
        safe_apply_buff(run, "Luck%", luck_amount)
        result.logs.append(f"{stat} +{amount:g}. Luck% +{luck_amount:g}.")
    elif handler == "wishing_well":
        options = event.get("_options") or generate_wishing_well_options(rng, run, stats)
        if not options:
            result.logs.append("The well is silent; its price would be too cruel.")
            return
        option = options[min(choice_index, len(options) - 1)]
        result.logs.append(apply_enhancement(run, option))


def _weighted_choice(rng: random.Random, encounters: list[dict]) -> dict:
    total = sum(float(encounter.get("weight", 1.0)) for encounter in encounters)
    point = rng.uniform(0, total)
    upto = 0.0
    for encounter in encounters:
        upto += float(encounter.get("weight", 1.0))
        if point <= upto:
            return encounter
    return encounters[-1]
