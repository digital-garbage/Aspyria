from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from ascii_climb.content import ENEMIES, LOCATIONS
from ascii_climb.leveling import queue_level_rewards
from ascii_climb.loot import roll_item
from ascii_climb.meta import effective_stats, final_gold_payout
from ascii_climb.models import EnemyTemplate, Item, MetaState, RunState, STAT_KEYS
from ascii_climb.relics import consume_relic_charge
from ascii_climb.state import decay_timed_modifiers, lock_stat, safe_apply_buff, sanitize_active_fight


@dataclass
class CombatResult:
    victory: bool
    enemy: EnemyTemplate
    enemy_hp: int
    enemy_atk: int
    logs: List[str]
    loot: Item | None = None
    xp: int = 0
    coins: int = 0
    gold_awarded: int = 0
    fled: bool = False
    player_hp: int = 0
    summary: List[str] | None = None
    events: List[dict] | None = None
    enemy_hp_left: int = 0
    consolation_item: Item | None = None
    consolation_buff: dict | None = None
    ongoing: bool = False
    run_success: bool = False
    run_failure: bool = False
    stat_locked: str = ""


@dataclass(frozen=True)
class ScoutPreview:
    enemy: EnemyTemplate
    enemy_hp: int
    enemy_atk: int
    xp: int
    coins: int
    danger: str
    lines: List[str]


STANCE_DESCRIPTIONS = {
    "steady": "Steady: balanced damage, no evasion change.",
    "guarded": "Guarded: -18% attack, -8% crit chance, +8% evasion.",
    "reckless": "Reckless: +22% attack, +8% crit chance, -8% evasion, 20% chance to break random equipped gear after each attack.",
}


def current_location(run: RunState):
    return LOCATIONS[run.location_index]


def next_enemy_template(rng: random.Random, run: RunState) -> EnemyTemplate:
    location = current_location(run)
    if run.fights_in_location >= location.fights_to_boss:
        return ENEMIES[location.boss_name]
    return ENEMIES[rng.choice(location.enemy_names)]


def get_or_create_active_fight(rng: random.Random, meta: MetaState, run: RunState) -> tuple[EnemyTemplate, dict]:
    active = sanitize_active_fight(run.active_fight)
    if active and active["enemy_name"] in ENEMIES:
        run.active_fight = active
        return ENEMIES[active["enemy_name"]], active
    enemy = next_enemy_template(rng, run)
    enemy_hp, enemy_atk, xp, coins = enemy_scale(meta, run, enemy)
    active = {
        "enemy_name": enemy.name,
        "enemy_hp": enemy_hp,
        "enemy_max_hp": enemy_hp,
        "enemy_atk": enemy_atk,
        "xp": xp,
        "coins": coins,
        "boss": enemy.boss,
        "seed": rng.getrandbits(32),
    }
    run.active_fight = active
    return enemy, active


def clear_active_fight(run: RunState) -> None:
    run.active_fight = None


def scout_preview(rng: random.Random, meta: MetaState, run: RunState) -> ScoutPreview:
    active = sanitize_active_fight(run.active_fight)
    if active and active["enemy_name"] in ENEMIES:
        enemy = ENEMIES[active["enemy_name"]]
        enemy_hp, enemy_atk, xp, coins = (
            int(active["enemy_hp"]),
            int(active["enemy_atk"]),
            int(active["xp"]),
            int(active["coins"]),
        )
        enemy_max_hp = int(active["enemy_max_hp"])
    else:
        enemy = next_enemy_template(rng, run)
        enemy_hp, enemy_atk, xp, coins = enemy_scale(meta, run, enemy)
        enemy_max_hp = enemy_hp
    stats = effective_stats(meta, run)
    player_power = max(1.0, stats.get("HP", 1.0) + stats.get("ATK", 1.0) * 8)
    enemy_power = enemy_hp + enemy_atk * 8
    ratio = enemy_power / player_power
    if ratio >= 1.35:
        danger = "deadly"
    elif ratio >= 0.95:
        danger = "dangerous"
    elif ratio >= 0.65:
        danger = "fair"
    else:
        danger = "manageable"
    traits = []
    if enemy.boss:
        traits.append("boss")
    if enemy.abilities:
        traits.extend(enemy.abilities)
    if enemy.multi_attack_chance:
        traits.append(f"{enemy.multi_attack_chance:g}% multi-attack")
    if enemy.evasion_chance:
        traits.append(f"{enemy.evasion_chance:g}% evasion")
    lines = [
        f"Scouting: next threat is {enemy.name}.",
        f"HP {enemy_hp}/{enemy_max_hp}, ATK {enemy_atk}, rewards {xp} XP and {coins} coins.",
        f"Danger: {danger}. Traits: {', '.join(traits) if traits else 'none'}.",
    ]
    return ScoutPreview(enemy, enemy_hp, enemy_atk, xp, coins, danger, lines)


def enemy_scale(meta: MetaState, run: RunState, enemy: EnemyTemplate) -> tuple[int, int, int, int]:
    stats = effective_stats(meta, run)
    location = current_location(run)
    loop_hp = 1 + (run.loop_tier - 1) * 0.46
    loop_atk = 1 + (run.loop_tier - 1) * 0.28
    greed = 1 + stats.get("Enemy Scaling%", 0.0) / 100
    hp = int(enemy.base_hp * location.difficulty * loop_hp * greed)
    atk = int(enemy.base_atk * (0.85 + location.difficulty * 0.18) * loop_atk * (1 + (greed - 1) * 0.8))
    reward_scale = location.difficulty * (1 + (run.loop_tier - 1) * 0.38) * greed
    xp = int(round(enemy.xp * reward_scale * (1 + stats.get("XP Boost%", 0.0) / 100)))
    coins = int(round(enemy.coins * reward_scale * (1 + stats.get("Coin Acquisition Boost%", 0.0) / 100)))
    if enemy.boss:
        hp = int(hp * 1.15)
        atk = int(atk * 1.08)
    return max(1, hp), max(1, atk), max(1, xp), max(1, coins)


def attack_count(rng: random.Random, chance: float) -> int:
    attacks = 1
    if rng.random() * 100 < chance:
        attacks += 1
    if rng.random() * 100 < max(0.0, chance - 35.0):
        attacks += 1
    return min(3, attacks)


def player_hit(rng: random.Random, stats: dict, stance: str) -> tuple[int, List[str]]:
    logs = []
    stance_atk = {"steady": 1.0, "guarded": 0.82, "reckless": 1.22}.get(stance, 1.0)
    crit_shift = 8 if stance == "reckless" else -8 if stance == "guarded" else 0
    damage = stats["ATK"] * stance_atk * rng.uniform(0.86, 1.14)
    if rng.random() * 100 < max(0.0, stats.get("CR%", 0.0) + crit_shift):
        damage *= 1 + stats.get("CD%", 0.0) / 100
        logs.append("critical")
        if rng.random() * 100 < stats.get("Megacrit Chance%", 0.0):
            damage *= 1 + stats.get("Megacrit Damage%", 0.0) / 100
            logs.append("MEGACRIT")
    return max(1, int(damage)), logs


def enemy_hit(rng: random.Random, enemy: EnemyTemplate, enemy_atk: int, stats: dict, stance: str) -> tuple[int, str]:
    evade_bonus = 8 if stance == "guarded" else -8 if stance == "reckless" else 0
    if rng.random() * 100 < stats.get("Evasion%", 0.0) + evade_bonus:
        return 0, "You evade the hit."
    damage = enemy_atk * rng.uniform(0.88, 1.12)
    if "rage" in enemy.abilities and rng.random() < 0.18:
        damage *= 1.45
    if "megacrit" in enemy.abilities and rng.random() < 0.08:
        damage *= 2.2
    if "armor_crack" in enemy.abilities:
        damage *= max(0.65, 1 - stats.get("Damage Reduction%", 0.0) / 180)
    else:
        damage *= max(0.55, 1 - stats.get("Damage Reduction%", 0.0) / 100)
    damage *= 1 + stats.get("Damage Taken%", 0.0) / 100
    damage_done = max(1, int(damage))
    return damage_done, f"{enemy.name} hits you for {damage_done}."


def enemy_dialogue(enemy: EnemyTemplate, key: str, fallback: str) -> str:
    return enemy.dialogue.get(key, fallback)


def maybe_break_reckless_item(rng: random.Random, run: RunState, logs: List[str]) -> dict | None:
    if rng.random() >= 0.20:
        return None
    equipped = run.equipped_items()
    if not equipped:
        return None
    item = rng.choice(equipped)
    for slot, equipped_item in run.equipment.items():
        if equipped_item and equipped_item.id == item.id:
            run.equipment[slot] = None
            message = f"Reckless strain shatters {item.name}."
            logs.append(message)
            return {
                "actor": "system",
                "message": message,
                "item_broken": True,
                "item_name": item.name,
                "item_slot": slot,
            }
    return None


def run_combat(
    rng: random.Random, meta: MetaState, run: RunState, stance: str = "steady"
) -> CombatResult:
    enemy, active_fight = get_or_create_active_fight(rng, meta, run)
    enemy_hp = int(active_fight["enemy_max_hp"])
    enemy_atk = int(active_fight["enemy_atk"])
    xp_reward = int(active_fight["xp"])
    coin_reward = int(active_fight["coins"])
    enemy_power = enemy_hp + enemy_atk * 6
    run.strongest_enemy_power = max(run.strongest_enemy_power, enemy_power)
    stats = effective_stats(meta, run)
    active_fight = run.active_fight or active_fight
    max_hp = int(stats["HP"])
    run.current_hp = min(max_hp, run.current_hp if run.current_hp > 0 else max_hp)
    hp_left = int(active_fight["enemy_hp"])
    logs = [enemy_dialogue(enemy, "intro", f"{enemy.name} appears in {current_location(run).name}.")]
    events = [
        {
            "actor": "system",
            "message": logs[0],
            "player_hp": run.current_hp,
            "player_max_hp": max_hp,
            "enemy_hp": hp_left,
            "enemy_max_hp": enemy_hp,
        }
    ]
    if enemy.boss:
        logs.append(enemy_dialogue(enemy, "boss_intro", f"{enemy.name} bars the road."))
        events.append(
            {
                "actor": "enemy",
                "message": logs[-1],
                "player_hp": run.current_hp,
                "player_max_hp": max_hp,
                "enemy_hp": hp_left,
                "enemy_max_hp": enemy_hp,
            }
        )

    if "copy_crit" in enemy.abilities:
        enemy_atk = int(enemy_atk * (1 + min(stats.get("CR%", 0.0), 60) / 220))
    if "evade" in enemy.abilities:
        logs.append(f"{enemy.name} is slippery. Some hits may miss.")

    for round_no in range(1, 41):
        attacks = attack_count(rng, stats.get("Multi-Attack Chance%", 0.0))
        for attack_no in range(attacks):
            evade_chance = enemy.evasion_chance or (12.0 if "evade" in enemy.abilities else 0.0)
            if rng.random() * 100 < evade_chance:
                message = enemy_dialogue(enemy, "defense", f"Round {round_no}: {enemy.name} slips away from your strike.")
                logs.append(message)
                events.append(
                    {
                        "actor": "player",
                        "message": message,
                        "damage": 0,
                        "dodge": True,
                        "player_hp": run.current_hp,
                        "player_max_hp": max_hp,
                        "enemy_hp": hp_left,
                        "enemy_max_hp": enemy_hp,
                    }
                )
                continue
            damage, tags = player_hit(rng, stats, stance)
            hp_left = max(0, hp_left - damage)
            active_fight["enemy_hp"] = hp_left
            tag_text = f" ({', '.join(tags)})" if tags else ""
            message = f"Round {round_no}: You deal {damage}{tag_text}. Enemy HP: {hp_left}/{enemy_hp}."
            logs.append(message)
            events.append(
                {
                    "actor": "player",
                    "message": message,
                    "damage": damage,
                    "tags": tags,
                    "player_hp": run.current_hp,
                    "player_max_hp": max_hp,
                    "enemy_hp": hp_left,
                    "enemy_max_hp": enemy_hp,
                }
            )
            if stance == "reckless":
                broken_event = maybe_break_reckless_item(rng, run, logs)
                if broken_event:
                    broken_event.update(
                        {
                            "player_hp": run.current_hp,
                            "player_max_hp": max_hp,
                            "enemy_hp": hp_left,
                            "enemy_max_hp": enemy_hp,
                        }
                    )
                    events.append(broken_event)
            if hp_left <= 0:
                break
            if attack_no == 0 and attacks > 1:
                logs.append("Your gear sparks into a second attack.")
        if hp_left <= 0:
            break

        enemy_multi = enemy.multi_attack_chance or (28.0 if "multi" in enemy.abilities else 0.0)
        enemy_attacks = attack_count(rng, enemy_multi)
        for _ in range(enemy_attacks):
            damage, line = enemy_hit(rng, enemy, enemy_atk, stats, stance)
            run.current_hp = max(0, run.current_hp - damage)
            if damage:
                attack_line = enemy_dialogue(enemy, "attack", line)
                message = f"{attack_line} Damage: {damage}. HP: {max(0, run.current_hp)}/{max_hp}."
                logs.append(message)
            else:
                message = line
                logs.append(message)
            events.append(
                {
                    "actor": "enemy",
                    "message": message,
                    "damage": damage,
                    "dodge": damage == 0,
                    "player_hp": max(0, run.current_hp),
                    "player_max_hp": max_hp,
                    "enemy_hp": hp_left,
                    "enemy_max_hp": enemy_hp,
                }
            )
            if run.current_hp <= 0:
                break
        if run.current_hp <= 0:
            break

    if hp_left <= 0:
        return handle_victory(rng, meta, run, enemy, enemy_hp, enemy_atk, xp_reward, coin_reward, logs, events)

    run.current_hp = 0
    logs.append("You collapse before the enemy does.")
    logs.append(enemy_dialogue(enemy, "player_loss", f"{enemy.name} leaves you broken."))
    gold = apply_defeat_penalty(rng, meta, run, logs)
    consolation_item, consolation_buff = grant_consolation_reward(rng, meta, run, logs)
    summary = [
        f"You were defeated by {enemy.name}.",
        f"{enemy.name} has {hp_left}/{enemy_hp} HP left.",
        f"HP left: 0/{max_hp}.",
    ]
    if run.active:
        summary.append(f"You recover to {run.current_hp}/{max_hp} HP.")
    if gold:
        summary.append(f"The run paid out {gold} gold.")
    decay_timed_modifiers(run)
    return CombatResult(
        False,
        enemy,
        enemy_hp,
        enemy_atk,
        logs,
        gold_awarded=gold,
        player_hp=max(0, run.current_hp),
        summary=summary,
        events=events,
        enemy_hp_left=hp_left,
        consolation_item=consolation_item,
        consolation_buff=consolation_buff,
        run_failure=not run.active,
    )


def run_combat_turn(
    rng: random.Random, meta: MetaState, run: RunState, stance: str = "steady", round_no: int = 1
) -> CombatResult:
    enemy, active_fight = get_or_create_active_fight(rng, meta, run)
    enemy_hp = int(active_fight["enemy_max_hp"])
    enemy_atk = int(active_fight["enemy_atk"])
    xp_reward = int(active_fight["xp"])
    coin_reward = int(active_fight["coins"])
    enemy_power = enemy_hp + enemy_atk * 6
    run.strongest_enemy_power = max(run.strongest_enemy_power, enemy_power)
    stats = effective_stats(meta, run)
    active_fight = run.active_fight or active_fight
    max_hp = int(stats["HP"])
    run.current_hp = min(max_hp, run.current_hp if run.current_hp > 0 else max_hp)
    hp_left = int(active_fight["enemy_hp"])
    logs = []
    events = []
    if round_no == 1:
        intro = enemy_dialogue(enemy, "intro", f"{enemy.name} appears in {current_location(run).name}.")
        logs.append(intro)
        events.append(_combat_event("system", intro, run.current_hp, max_hp, hp_left, enemy_hp))
        if enemy.boss:
            boss_intro = enemy_dialogue(enemy, "boss_intro", f"{enemy.name} bars the road.")
            logs.append(boss_intro)
            events.append(_combat_event("enemy", boss_intro, run.current_hp, max_hp, hp_left, enemy_hp))
    if "copy_crit" in enemy.abilities:
        enemy_atk = int(enemy_atk * (1 + min(stats.get("CR%", 0.0), 60) / 220))

    attacks = attack_count(rng, stats.get("Multi-Attack Chance%", 0.0))
    for attack_no in range(attacks):
        evade_chance = enemy.evasion_chance or (12.0 if "evade" in enemy.abilities else 0.0)
        if rng.random() * 100 < evade_chance:
            message = enemy_dialogue(enemy, "defense", f"Round {round_no}: {enemy.name} slips away from your strike.")
            logs.append(message)
            events.append(_combat_event("player", message, run.current_hp, max_hp, hp_left, enemy_hp, damage=0, dodge=True))
            continue
        damage, tags = player_hit(rng, stats, stance)
        hp_left = max(0, hp_left - damage)
        active_fight["enemy_hp"] = hp_left
        tag_text = f" ({', '.join(tags)})" if tags else ""
        message = f"Round {round_no} [{stance}]: You deal {damage}{tag_text}. Enemy HP: {hp_left}/{enemy_hp}."
        logs.append(message)
        events.append(_combat_event("player", message, run.current_hp, max_hp, hp_left, enemy_hp, damage=damage, tags=tags))
        if stance == "reckless":
            broken_event = maybe_break_reckless_item(rng, run, logs)
            if broken_event:
                broken_event.update(
                    {
                        "player_hp": run.current_hp,
                        "player_max_hp": max_hp,
                        "enemy_hp": hp_left,
                        "enemy_max_hp": enemy_hp,
                    }
                )
                events.append(broken_event)
        if hp_left <= 0:
            break
        if attack_no == 0 and attacks > 1:
            logs.append("Your gear sparks into a second attack.")

    if hp_left <= 0:
        return handle_victory(rng, meta, run, enemy, enemy_hp, enemy_atk, xp_reward, coin_reward, logs, events)

    enemy_multi = enemy.multi_attack_chance or (28.0 if "multi" in enemy.abilities else 0.0)
    enemy_attacks = attack_count(rng, enemy_multi)
    for _ in range(enemy_attacks):
        damage, line = enemy_hit(rng, enemy, enemy_atk, stats, stance)
        run.current_hp = max(0, run.current_hp - damage)
        if damage:
            attack_line = enemy_dialogue(enemy, "attack", line)
            message = f"{attack_line} Damage: {damage}. HP: {max(0, run.current_hp)}/{max_hp}."
        else:
            message = line
        logs.append(message)
        events.append(_combat_event("enemy", message, max(0, run.current_hp), max_hp, hp_left, enemy_hp, damage=damage, dodge=damage == 0))
        if run.current_hp <= 0:
            break

    if run.current_hp <= 0:
        run.current_hp = 0
        logs.append("You collapse before the enemy does.")
        logs.append(enemy_dialogue(enemy, "player_loss", f"{enemy.name} leaves you broken."))
        gold = apply_defeat_penalty(rng, meta, run, logs)
        consolation_item, consolation_buff = grant_consolation_reward(rng, meta, run, logs)
        summary = [
            f"You were defeated by {enemy.name}.",
            f"{enemy.name} has {hp_left}/{enemy_hp} HP left.",
            f"HP left: 0/{max_hp}.",
        ]
        if run.active:
            summary.append(f"You recover to {run.current_hp}/{max_hp} HP.")
        if gold:
            summary.append(f"The run paid out {gold} gold.")
        decay_timed_modifiers(run)
        return CombatResult(
            False,
            enemy,
            enemy_hp,
            enemy_atk,
            logs,
            gold_awarded=gold,
            player_hp=max(0, run.current_hp),
            summary=summary,
            events=events,
            enemy_hp_left=hp_left,
            consolation_item=consolation_item,
            consolation_buff=consolation_buff,
            run_failure=not run.active,
        )

    return CombatResult(
        False,
        enemy,
        enemy_hp,
        enemy_atk,
        logs,
        player_hp=run.current_hp,
        summary=[f"{enemy.name} has {hp_left}/{enemy_hp} HP left."],
        events=events,
        enemy_hp_left=hp_left,
        ongoing=True,
    )


def _combat_event(
    actor: str,
    message: str,
    player_hp: int,
    player_max_hp: int,
    enemy_hp: int,
    enemy_max_hp: int,
    damage: int = 0,
    dodge: bool = False,
    tags: list | None = None,
) -> dict:
    return {
        "actor": actor,
        "message": message,
        "damage": damage,
        "dodge": dodge,
        "tags": tags or [],
        "player_hp": player_hp,
        "player_max_hp": player_max_hp,
        "enemy_hp": enemy_hp,
        "enemy_max_hp": enemy_max_hp,
    }


def handle_victory(
    rng: random.Random,
    meta: MetaState,
    run: RunState,
    enemy: EnemyTemplate,
    enemy_hp: int,
    enemy_atk: int,
    xp_reward: int,
    coin_reward: int,
    logs: List[str],
    events: List[dict] | None = None,
    victory_line: str | None = None,
) -> CombatResult:
    stats = effective_stats(meta, run)
    hp_before_heal = run.current_hp
    run.xp += xp_reward
    run.coins += coin_reward
    if enemy.corrupted:
        run.corrupted_kills += 1
    run.enemies_killed += 1
    levels_gained = []
    while run.xp >= run.level * 100:
        run.xp -= run.level * 100
        run.level += 1
        levels_gained.append(run.level)
        logs.append(f"Level up. You are now level {run.level}.")
    queue_level_rewards(run, levels_gained, boss_defeated=enemy.boss)
    heal_rate = (0.08 if not enemy.boss else 0.18) + run.post_fight_heal_bonus
    heal = max(3, int(effective_stats(meta, run)["HP"] * heal_rate))
    max_hp = int(effective_stats(meta, run)["HP"])
    run.current_hp = max_hp if enemy.boss else min(max_hp, run.current_hp + heal)
    restored = max(0, run.current_hp - hp_before_heal)

    loot_chance = 0.65 + min(0.28, stats.get("Luck%", 0.0) / 350) + run.loot_bonus_chance
    if enemy.family == "Necromancers" or enemy.corrupted:
        loot_chance += run.loot_bonus_chance
    if enemy.boss:
        loot_chance = 1.0
    loot = None
    if rng.random() < loot_chance:
        force = "rare" if enemy.boss and run.loop_tier == 1 else None
        loot = roll_item(rng, run, stats.get("Luck%", 0.0), stats.get("Enemy Scaling%", 0.0), force)
        run.best_item_value = max(run.best_item_value, loot.value)

    logs.append(victory_line or enemy_dialogue(enemy, "player_victory", f"{enemy.name} falls."))
    logs.append(f"+{xp_reward} XP, +{coin_reward} coins.")
    logs.append(f"You restore {restored} HP after the fight. HP: {run.current_hp}/{max_hp}.")
    run_success = False
    if enemy.boss:
        run.completed_bosses += 1
        run.fights_in_location = 0
        run.location_index += 1
        if run.location_index >= len(LOCATIONS):
            run.location_index = 0
            run.loop_tier += 1
            run_success = run.loop_tier >= 2 and not run.first_loop_clear_recorded
            logs.append(f"The route folds back to Rust Alley. Loop tier {run.loop_tier} begins.")
        else:
            logs.append(f"New location unlocked: {current_location(run).name}.")
        logs.append(enemy_dialogue(enemy, "boss_victory", "The King's banner advances."))
    else:
        run.fights_in_location += 1
        if run.fights_in_location >= current_location(run).fights_to_boss:
            logs.append("The local boss has noticed you.")

    summary = [
        f"You defeated {enemy.name}.",
        f"You received {xp_reward} XP and {coin_reward} coins.",
        f"You restored {restored} HP.",
    ]
    if loot:
        summary.append(f"You got {loot.quality} quality {loot.rarity} {loot.name}.")
    else:
        summary.append("You found no gear this time.")
    if run.pending_level_rewards:
        summary.append(f"Level rewards waiting: {len(run.pending_level_rewards)}.")
    clear_active_fight(run)
    decay_timed_modifiers(run)

    return CombatResult(
        True,
        enemy,
        enemy_hp,
        enemy_atk,
        logs,
        loot=loot,
        xp=xp_reward,
        coins=coin_reward,
        player_hp=run.current_hp,
        summary=summary,
        events=events or [],
        enemy_hp_left=0,
        run_success=run_success,
    )


def flee_from_combat(rng: random.Random, meta: MetaState, run: RunState) -> CombatResult:
    enemy, active_fight = get_or_create_active_fight(rng, meta, run)
    enemy_hp = int(active_fight["enemy_max_hp"])
    enemy_atk = int(active_fight["enemy_atk"])
    xp_reward = int(active_fight["xp"])
    coin_reward = int(active_fight["coins"])
    enemy_hp_left = int(active_fight["enemy_hp"])
    logs = [f"You flee from {enemy.name}. It keeps {enemy_hp_left}/{enemy_hp} HP."]
    if rng.random() < 0.06:
        logs = ["You have managed to walk past the enemy undetected. This will not end well in the future."]
        stat = rng.choice(STAT_KEYS)
        lock_stat(run, stat)
        logs.append(f"{stat} is now locked for the rest of this run.")
        result = handle_victory(
            rng,
            meta,
            run,
            enemy,
            enemy_hp,
            enemy_atk,
            xp_reward,
            coin_reward,
            logs,
            victory_line=f"You slip past {enemy.name} and leave the danger for later.",
        )
        result.fled = True
        result.stat_locked = stat
        result.summary = result.summary or []
        if result.summary:
            result.summary.insert(0, "Undetected escape counted as a victory.")
        return result
    protected = consume_relic_charge(run, "flee_protection") or run.relic_charges_used.get("perk_flee_protection", 0) < 0
    if run.relic_charges_used.get("perk_flee_protection", 0) < 0:
        run.relic_charges_used["perk_flee_protection"] += 1
    penalty = rng.choice(["coins", "hp", "item", "stat"])
    if protected:
        logs.append("Saint's Refuge softens the price of escape.")
        penalty = "coins" if penalty in {"item", "stat"} else penalty
    if penalty == "coins":
        loss = min(run.coins, max(5, 8 + run.loop_tier * 6))
        run.coins -= loss
        logs.append(f"You lose {loss} coins in the retreat.")
    elif penalty == "hp":
        max_hp = int(effective_stats(meta, run)["HP"])
        loss = max(1, int(max_hp * (0.12 if protected else 0.25)))
        run.current_hp = max(1, run.current_hp - loss)
        logs.append(f"You lose {loss} HP escaping.")
    elif penalty == "item":
        all_items = run.inventory + run.equipped_items()
        if all_items:
            lost = rng.choice(all_items)
            if lost in run.inventory:
                run.inventory.remove(lost)
            else:
                for slot, item in run.equipment.items():
                    if item and item.id == lost.id:
                        run.equipment[slot] = None
                        break
            logs.append(f"You drop {lost.name} while fleeing.")
        else:
            logs.append("You have no item to lose; the curse takes coins instead.")
            run.coins = max(0, run.coins - min(run.coins, 10))
    else:
        stat = rng.choice(STAT_KEYS)
        run.run_debuffs.setdefault(stat, 0.0)
        logs.append(f"{stat} will not accept further boosts this run.")
    consolation_item, consolation_buff = grant_consolation_reward(rng, meta, run, logs)
    decay_timed_modifiers(run)
    return CombatResult(
        False,
        enemy,
        enemy_hp,
        enemy_atk,
        logs,
        fled=True,
        player_hp=run.current_hp,
        summary=list(logs),
        events=[],
        enemy_hp_left=enemy_hp_left,
        consolation_item=consolation_item,
        consolation_buff=consolation_buff,
    )


def grant_consolation_reward(
    rng: random.Random, meta: MetaState, run: RunState, logs: List[str]
) -> tuple[Item | None, dict | None]:
    if not run.active or rng.random() >= 0.5:
        return None, None
    stats = effective_stats(meta, run)
    if rng.random() < 0.5:
        item = roll_item(rng, run, stats.get("Luck%", 0.0), stats.get("Enemy Scaling%", 0.0))
        logs.append(f"In the chaos, you recover {item.label()}.")
        return item, None
    stat = rng.choice([key for key in STAT_KEYS if key != "Enemy Scaling%"])
    amount = 4.0 if stat in {"ATK", "HP"} else 2.0
    if stat in {"CD%", "Megacrit Damage%"}:
        amount = 6.0
    safe_apply_buff(run, stat, amount)
    buff = {"stat": stat, "amount": amount}
    logs.append(f"Desperation teaches you something: {stat} +{amount:g}.")
    return None, buff


def apply_defeat_penalty(rng: random.Random, meta: MetaState, run: RunState, logs: List[str]) -> int:
    run.defeats += 1
    if run.defeats == 1:
        all_items = run.inventory + run.equipped_items()
        if all_items:
            lost = max(all_items, key=lambda item: item.value)
            if lost in run.inventory:
                run.inventory.remove(lost)
            else:
                for slot, item in run.equipment.items():
                    if item and item.id == lost.id:
                        run.equipment[slot] = None
                        break
            logs.append(f"First defeat curse: {lost.name}, your most valuable gear, is gone.")
        else:
            logs.append("First defeat curse finds no gear to take.")
    elif run.defeats == 2:
        run.coins = 0
        logs.append("Second defeat curse: every coin in the run is gone.")
    elif run.defeats == 3:
        choices = rng.sample(STAT_KEYS, 2)
        for stat in choices:
            penalty = 18.0 if stat not in {"ATK", "HP"} else 30.0
            run.run_debuffs[stat] = run.run_debuffs.get(stat, 0.0) + penalty
        logs.append(f"Third defeat curse: {choices[0]} and {choices[1]} are scarred for this run.")
    else:
        gold = final_gold_payout(meta, run)
        meta.gold += gold
        run.active = False
        logs.append(f"Fourth defeat. The run ends and pays out {gold} gold.")
        return gold
    run.current_hp = max(1, int(effective_stats(meta, run)["HP"] * 0.30))
    logs.append(f"You recover to {run.current_hp}/{int(effective_stats(meta, run)['HP'])} HP.")
    return 0
