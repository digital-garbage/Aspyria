import random
import unittest
from pathlib import Path

from ascii_climb.combat import (
    STANCE_DESCRIPTIONS,
    attack_count,
    clear_active_fight,
    enemy_scale,
    enemy_hit,
    flee_from_combat,
    get_or_create_active_fight,
    maybe_break_reckless_item,
    percent_triggers,
    player_hit,
    run_combat,
    run_combat_turn,
    scout_preview,
)
from ascii_climb.content import ENEMIES, LOCATIONS, STORY
from ascii_climb.encounters import random_event
from ascii_climb.ilevel import current_ilevel_range, gear_advantage_bonuses
from ascii_climb.leveling import (
    apply_level_reward,
    describe_level_reward,
    describe_level_reward_for_run,
    generate_level_reward_options,
    queue_level_rewards,
)
from ascii_climb.loot import corrupted_chance_percent, roll_item, special_quality_chance_percent
from ascii_climb.meta import effective_stats
from ascii_climb.models import Item, MetaState, RunState
from ascii_climb.progression import EnhancementOption, describe_enhancement
from ascii_climb.relics import apply_passive_relics
from ascii_climb.shops import buy_medkit, buy_random_gear, equip_item, get_or_create_random_gear_offer, medkit_cost
from ascii_climb.sound import SoundManager
from ascii_climb.visuals import item_colors, readable_text_for_backgrounds


class LevelRewardTests(unittest.TestCase):
    def test_level_rewards_queue_normal_and_perks(self):
        run = RunState(level=5)
        queue_level_rewards(run, [2, 5], boss_defeated=True)
        self.assertEqual([reward["type"] for reward in run.pending_level_rewards], ["stat", "perk", "perk"])

    def test_normal_reward_applies_run_buff(self):
        run = RunState()
        message = apply_level_reward(run, {"type": "stat", "title": "Test ATK", "stat": "ATK", "amount": 3})
        self.assertIn("Attack: +3", message)
        self.assertEqual(run.run_buffs["ATK"], 3)

    def test_relic_multiplier_boosts_level_reward(self):
        run = RunState()
        run.equipment["relic"] = Item("r", "Royal Drillmark", "relic", "rare", "used", 1, {}, value=1)
        apply_passive_relics(run)
        apply_level_reward(run, {"type": "stat", "title": "Test ATK", "stat": "ATK", "amount": 3})
        self.assertEqual(run.run_buffs["ATK"], 6)

    def test_favored_stat_can_appear_in_options(self):
        run = RunState(favored_stat="ATK")
        options = generate_level_reward_options(random.Random(1), run, {"type": "stat"})
        self.assertTrue(options)

    def test_vampirism_is_not_a_level_reward_option(self):
        run = RunState(favored_stat="Vampirism%")
        options = generate_level_reward_options(random.Random(1), run, {"type": "stat"})
        self.assertTrue(options)
        self.assertNotIn("Vampirism%", {option.get("stat") for option in options})

    def test_perk_reward_descriptions_show_real_effects(self):
        reward = {"title": "Royal Purse", "effect": "bonus_coins", "params": {"coins": 60}}
        self.assertEqual(describe_level_reward(reward), "Royal Purse: gain 60 coins immediately")
        run = RunState()
        message = apply_level_reward(run, reward)
        self.assertIn("Royal Purse", message)
        self.assertEqual(run.coins, 60)

    def test_locked_stat_level_reward_displays_zero(self):
        run = RunState(locked_stats=["ATK"])
        text = describe_level_reward_for_run(run, {"type": "stat", "title": "Test ATK", "stat": "ATK", "amount": 3})
        self.assertIn("+0", text)
        self.assertIn("[LOCKED]", text)


class ILevelTests(unittest.TestCase):
    def test_ilevel_range_uses_location_loop_and_enemy_scaling(self):
        run = RunState(location_index=1, loop_tier=2)
        low = current_ilevel_range(run, 0)
        high = current_ilevel_range(run, 32)
        self.assertGreater(high[0], low[0])
        self.assertGreater(high[1], low[1])

    def test_gear_advantage_adds_stats_above_location_minimum(self):
        run = RunState(location_index=0)
        run.equipment["weapon"] = Item("w", "Test Sword", "weapon", "rare", "used", 7, {"ATK": 1}, value=1)
        bonuses = gear_advantage_bonuses(run)
        self.assertGreater(bonuses["ATK"], 0)
        self.assertGreater(effective_stats(MetaState(), run)["Luck%"], 0)


class CombatFlowTests(unittest.TestCase):
    def test_sub_100_multi_attack_can_reach_two(self):
        counts = {attack_count(random.Random(seed), 95) for seed in range(40)}
        self.assertIn(2, counts)

    def test_over_100_multi_attack_grants_guaranteed_extra_attacks(self):
        self.assertEqual(attack_count(random.Random(1), 100), 2)
        self.assertEqual(attack_count(random.Random(1), 200), 3)
        counts = {attack_count(random.Random(seed), 150) for seed in range(30)}
        self.assertEqual(counts, {2, 3})

    def test_percent_triggers_supports_over_100_rolls(self):
        self.assertEqual(percent_triggers(random.Random(1), 220), 3)
        self.assertEqual(percent_triggers(random.Random(2), 220), 2)

    def test_run_combat_queues_level_reward(self):
        run = RunState(seed=1, xp=95)
        run.run_buffs["ATK"] = 1000
        result = run_combat(random.Random(2), MetaState(), run)
        self.assertTrue(result.victory)
        self.assertTrue(run.pending_level_rewards)

    def test_flee_applies_penalty(self):
        run = RunState(seed=1, coins=50, current_hp=100)
        result = flee_from_combat(random.Random(1), MetaState(), run)
        self.assertTrue(result.fled)
        self.assertTrue(result.logs)

    def test_undetected_flee_counts_as_victory_and_locks_stat(self):
        class ScriptedRandom(random.Random):
            def random(self):
                return 0.0

        run = RunState(seed=1)
        result = flee_from_combat(ScriptedRandom(1), MetaState(), run)
        self.assertTrue(result.victory)
        self.assertTrue(result.fled)
        self.assertTrue(result.stat_locked)
        self.assertIn(result.stat_locked, run.locked_stats)
        self.assertIsNone(run.active_fight)

    def test_stance_descriptions_include_guarded_and_reckless_tradeoffs(self):
        self.assertIn("-8% crit", STANCE_DESCRIPTIONS["guarded"])
        self.assertIn("-8% evasion", STANCE_DESCRIPTIONS["reckless"])
        self.assertIn("20% chance", STANCE_DESCRIPTIONS["reckless"])

    def test_enemy_hit_log_can_show_damage_and_hp_after_application(self):
        run = RunState(current_hp=50)
        enemy = ENEMIES[LOCATIONS[0].enemy_names[0]]
        damage, line = enemy_hit(random.Random(4), enemy, 10, {"Evasion%": 0.0}, "steady")
        run.current_hp -= damage
        full_line = f"{line} Damage: {damage}. HP: {run.current_hp}/50."
        self.assertIn("Damage:", full_line)
        self.assertIn("HP:", full_line)

    def test_over_100_evasion_guarantees_evade(self):
        enemy = ENEMIES[LOCATIONS[0].enemy_names[0]]
        damage, line = enemy_hit(random.Random(2), enemy, 999, {"Evasion%": 100.0}, "steady")
        self.assertEqual(damage, 0)
        self.assertIn("evade", line.lower())

    def test_overcrit_adds_repeated_crit_damage_chunks(self):
        class FlatRandom(random.Random):
            def uniform(self, a, b):
                return 1.0

            def random(self):
                return 0.99

        damage, tags = player_hit(
            FlatRandom(1),
            {"ATK": 100.0, "CR%": 220.0, "CD%": 50.0, "Megacrit Chance%": 0.0},
            "steady",
        )
        self.assertEqual(damage, 200)
        self.assertIn("critical x2", tags)

    def test_reckless_can_break_equipped_item(self):
        run = RunState()
        run.equipment["weapon"] = Item("w", "Test Blade", "weapon", "common", "used", 1, {"ATK": 1}, value=1)
        logs = []
        event = maybe_break_reckless_item(random.Random(1), run, logs)
        self.assertIsNone(run.equipment["weapon"])
        self.assertIn("shatters", logs[0])
        self.assertTrue(event["item_broken"])
        self.assertEqual(event["item_slot"], "weapon")

    def test_scout_preview_does_not_mutate_run_counter(self):
        run = RunState(seed=12, rng_counter=3)
        preview = scout_preview(random.Random(5), MetaState(), run)
        self.assertEqual(run.rng_counter, 3)
        self.assertIn(preview.enemy.name, preview.lines[0])
        self.assertIn("HP", preview.lines[1])

    def test_victory_result_has_summary(self):
        run = RunState(seed=1)
        run.run_buffs["ATK"] = 1000
        result = run_combat(random.Random(2), MetaState(), run)
        self.assertTrue(result.summary)
        self.assertIn("You defeated", result.summary[0])
        self.assertTrue(any("restored" in line.lower() for line in result.summary))

    def test_victory_logs_report_restored_hp(self):
        run = RunState(seed=1, current_hp=40)
        run.run_buffs["ATK"] = 1000
        result = run_combat(random.Random(2), MetaState(), run)
        self.assertTrue(result.victory)
        self.assertTrue(any("restore" in line.lower() and "HP:" in line for line in result.logs))

    def test_active_fight_persists_enemy_hp_after_loss(self):
        run = RunState(seed=1, current_hp=10)
        run.active_fight = {
            "enemy_name": LOCATIONS[0].enemy_names[0],
            "enemy_hp": 80,
            "enemy_max_hp": 80,
            "enemy_atk": 999,
            "xp": 1,
            "coins": 1,
            "boss": False,
            "seed": 1,
        }
        result = run_combat(random.Random(3), MetaState(), run)
        self.assertFalse(result.victory)
        self.assertIsNotNone(run.active_fight)
        self.assertLess(run.active_fight["enemy_hp"], 80)

    def test_defeat_recovers_to_thirty_percent_hp(self):
        run = RunState(seed=1, current_hp=10)
        run.active_fight = {
            "enemy_name": LOCATIONS[0].enemy_names[0],
            "enemy_hp": 80,
            "enemy_max_hp": 80,
            "enemy_atk": 999,
            "xp": 1,
            "coins": 1,
            "boss": False,
            "seed": 1,
        }
        result = run_combat(random.Random(3), MetaState(), run)
        self.assertFalse(result.victory)
        self.assertEqual(run.current_hp, int(effective_stats(MetaState(), run)["HP"] * 0.30))
        self.assertTrue(any("recover to" in line.lower() for line in result.summary))

    def test_flee_keeps_same_active_enemy(self):
        run = RunState(seed=1)
        enemy, active = get_or_create_active_fight(random.Random(4), MetaState(), run)
        result = flee_from_combat(random.Random(5), MetaState(), run)
        self.assertTrue(result.fled)
        self.assertEqual(run.active_fight["enemy_name"], enemy.name)
        self.assertEqual(run.active_fight["enemy_hp"], active["enemy_hp"])

    def test_victory_clears_active_fight(self):
        run = RunState(seed=1)
        run.run_buffs["ATK"] = 1000
        get_or_create_active_fight(random.Random(4), MetaState(), run)
        result = run_combat(random.Random(2), MetaState(), run)
        self.assertTrue(result.victory)
        self.assertIsNone(run.active_fight)

    def test_combat_turn_can_continue_without_resolving(self):
        run = RunState(seed=1, current_hp=100)
        run.active_fight = {
            "enemy_name": LOCATIONS[0].enemy_names[0],
            "enemy_hp": 500,
            "enemy_max_hp": 500,
            "enemy_atk": 1,
            "xp": 1,
            "coins": 1,
            "boss": False,
            "seed": 1,
        }
        result = run_combat_turn(random.Random(3), MetaState(), run, "guarded", 1)
        self.assertTrue(result.ongoing)
        self.assertLess(run.active_fight["enemy_hp"], 500)


class LootLuckTests(unittest.TestCase):
    def test_luck_controls_corrupted_and_top_quality_chance(self):
        self.assertEqual(corrupted_chance_percent(0, 0, 1), 1.0)
        self.assertEqual(corrupted_chance_percent(20, 0, 1), 6.0)
        self.assertEqual(special_quality_chance_percent(0, 1), 1.0)
        self.assertEqual(special_quality_chance_percent(20, 1), 6.0)

    def test_random_gear_failure_adds_pity_bonus(self):
        run = RunState(coins=100000)
        ok, message = buy_random_gear(random.Random(7), MetaState(), run, 0, 0)
        self.assertFalse(ok)
        self.assertIn("No refunds", message)
        self.assertEqual(run.random_gear_failures, 1)

    def test_random_gear_offer_price_is_stable_until_consumed(self):
        run = RunState(coins=0)
        first = get_or_create_random_gear_offer(random.Random(1), run, 0, 0)
        second = get_or_create_random_gear_offer(random.Random(2), run, 100, 0)
        self.assertEqual(first[0].id, second[0].id)
        self.assertEqual(first[1], second[1])

    def test_item_color_mapping_uses_rarity_and_quality(self):
        item = Item("1", "Test", "weapon", "legendary", "special craft", 1, {}, value=1)
        self.assertEqual(item_colors(item), ("#f59f2a", "#d94444"))

    def test_white_background_prefers_dark_text(self):
        self.assertEqual(readable_text_for_backgrounds("#f2f2f2", "#3d7bff"), "#111111")
        self.assertEqual(readable_text_for_backgrounds("#3d7bff", "#d94444"), "#ffffff")

    def test_early_items_feel_stronger_than_old_floor(self):
        item = roll_item(random.Random(2), RunState(seed=1), 0.0, 0.0, force_rarity="common", force_quality="used")
        self.assertGreaterEqual(max(abs(value) for value in item.stats.values()), 2)


class HpAndEventTests(unittest.TestCase):
    def test_hp_item_increases_current_hp_when_equipped(self):
        run = RunState(current_hp=40)
        item = Item("1", "Health Ring", "ring", "rare", "used", 1, {"HP": 4}, value=1)
        run.inventory.append(item)
        equip_item(run, item)
        self.assertEqual(run.current_hp, 44)

    def test_medkit_cost_doubles_after_purchase(self):
        run = RunState(coins=1000, current_hp=20)
        self.assertEqual(medkit_cost(run, "small"), 20)
        ok, message = buy_medkit(run, 100, "small")
        self.assertTrue(ok, message)
        self.assertEqual(run.current_hp, 40)


class PresentationAndAudioTests(unittest.TestCase):
    def test_sound_manager_tracks_music_key_without_audio_backend(self):
        manager = SoundManager(Path("assets/sounds"), sfx_volume=70, music_root=Path("assets/music"), music_volume=60)
        manager.play("click")
        self.assertEqual(manager.last_effect_key, "click")
        manager.set_music("menu")
        self.assertEqual(manager.current_music_key, "menu")
        self.assertAlmostEqual(manager.sfx_volume, 0.7)
        self.assertAlmostEqual(manager.music_volume, 0.6)

    def test_opening_balance_values_stay_softened(self):
        meta = MetaState()
        first_loop_boss = enemy_scale(meta, RunState(seed=1), ENEMIES["Barrow Knight"])
        second_loop_mob = enemy_scale(meta, RunState(seed=1, loop_tier=2), ENEMIES["Grave Thrall"])
        self.assertEqual(first_loop_boss[:2], (142, 12))
        self.assertEqual(second_loop_mob[:2], (67, 9))

    def test_random_event_handler_dispatches_from_json_shape(self):
        run = RunState(seed=1)
        event = {
            "title": "Old Monk",
            "handler": "old_monk",
            "body": "A monk nods.",
        }
        result = random_event(random.Random(1), MetaState(), run, event=event)
        self.assertIsNotNone(result)
        self.assertGreater(run.run_buffs.get("Luck%", 0), 0)

    def test_locked_stat_enhancement_displays_zero(self):
        run = RunState(locked_stats=["ATK"])
        option = EnhancementOption("Locked ATK", {"ATK": 5}, {}, "common")
        text = describe_enhancement(option, run)
        self.assertIn("+0", text)
        self.assertIn("[LOCKED]", text)


class StoryContentTests(unittest.TestCase):
    def test_story_and_dialogue_loaded(self):
        self.assertIn("Aspyria", STORY["intro"])
        enemy = ENEMIES[LOCATIONS[0].enemy_names[0]]
        self.assertIn("intro", enemy.dialogue)
        self.assertGreater(LOCATIONS[0].max_ilevel, LOCATIONS[0].min_ilevel)


if __name__ == "__main__":
    unittest.main()
