import random
import unittest

from ascii_climb.combat import apply_defeat_penalty, enemy_scale, run_combat
from ascii_climb.content import ENEMIES, LOCATIONS
from ascii_climb.loot import roll_item
from ascii_climb.meta import (
    buy_inventory_slot,
    buy_upgrade,
    effective_stats,
    final_gold_payout,
    refund_inventory_slot,
    refund_upgrade,
    upgrade_bonus_for_level,
    upgrade_cost,
)
from ascii_climb.models import Item, MetaState, RunState, SaveData
from ascii_climb.progression import EnhancementOption, apply_enhancement
from ascii_climb.save import load_game, save_game
from ascii_climb.shops import add_item_to_inventory, craft_fusion, equip_item


class CoreFormulaTests(unittest.TestCase):
    def test_upgrade_cost_bonus_and_refund(self):
        meta = MetaState(gold=124)
        self.assertEqual(upgrade_bonus_for_level(3), 6)
        self.assertEqual(upgrade_cost("ATK", 1), 4)
        self.assertEqual(upgrade_cost("ATK", 2), 20)
        self.assertEqual(upgrade_cost("ATK", 3), 100)

        self.assertTrue(buy_upgrade(meta, "ATK")[0])
        self.assertTrue(buy_upgrade(meta, "ATK")[0])
        self.assertTrue(buy_upgrade(meta, "ATK")[0])
        self.assertEqual(meta.gold, 0)
        self.assertEqual(meta.upgrades["ATK"], 3)
        self.assertTrue(refund_upgrade(meta, "ATK")[0])
        self.assertEqual(meta.gold, 50)
        self.assertEqual(meta.upgrades["ATK"], 2)

    def test_inventory_slot_buy_and_refund(self):
        meta = MetaState(gold=100)
        self.assertTrue(buy_inventory_slot(meta)[0])
        self.assertEqual(meta.inventory_capacity(), 13)
        self.assertTrue(refund_inventory_slot(meta)[0])
        self.assertEqual(meta.inventory_capacity(), 12)
        self.assertEqual(meta.gold, 87)


class GearSetTests(unittest.TestCase):
    def test_partial_and_full_set_bonuses_are_equipped_only(self):
        meta = MetaState()
        run = RunState(seed=1)
        armor = Item("1", "Royal Cuirass", "armor", "rare", "used", 1, {}, "Highcrown Vanguard", 10)
        boots = Item("2", "Royal Greaves", "boots", "rare", "used", 1, {}, "Highcrown Vanguard", 10)
        charm = Item("3", "Royal Talisman", "charm", "rare", "used", 1, {}, "Highcrown Vanguard", 10)
        run.inventory = [armor, boots, charm]

        equip_item(run, armor)
        self.assertEqual(effective_stats(meta, run)["Evasion%"], 6)
        equip_item(run, boots)
        self.assertEqual(effective_stats(meta, run)["Evasion%"], 9)
        equip_item(run, charm)
        self.assertEqual(effective_stats(meta, run)["Evasion%"], 53)

    def test_run_enhancement_applies_and_debuff_blocks_boost(self):
        run = RunState(seed=1)
        apply_enhancement(run, EnhancementOption("Small ATK", {"ATK": 5}, {}))
        self.assertEqual(run.run_buffs["ATK"], 5)
        run.run_debuffs["CR%"] = 18
        apply_enhancement(run, EnhancementOption("Blocked CR", {"CR%": 5}, {}))
        self.assertNotIn("CR%", run.run_buffs)


class RunSystemTests(unittest.TestCase):
    def test_enemy_scaling_affects_danger_and_rewards(self):
        run = RunState(seed=1)
        normal = MetaState()
        greedy = MetaState()
        greedy.upgrades["Enemy Scaling%"] = 3

        rng = random.Random(2)
        enemy = run_combat(rng, normal, run, "steady").enemy
        low = enemy_scale(normal, RunState(seed=1), enemy)
        high = enemy_scale(greedy, RunState(seed=1), enemy)
        self.assertGreater(high[0], low[0])
        self.assertGreater(high[2], low[2])
        self.assertGreater(high[3], low[3])

    def test_loop_scaling_is_less_spiky_than_before(self):
        enemy = LOCATIONS[0].enemy_names[0]
        base_hp, base_atk, _, _ = enemy_scale(MetaState(), RunState(seed=1), ENEMIES[enemy])
        loop_hp, loop_atk, _, _ = enemy_scale(MetaState(), RunState(seed=1, loop_tier=2), ENEMIES[enemy])
        self.assertLess(loop_hp / base_hp, 1.5)
        self.assertLess(loop_atk / base_atk, 1.3)

    def test_location_loops_after_final_boss(self):
        run = RunState(seed=1, location_index=len(LOCATIONS) - 1, fights_in_location=3)
        meta = MetaState()
        run.run_buffs["ATK"] = 10000
        result = run_combat(random.Random(9), meta, run, "reckless")
        self.assertTrue(result.victory)
        self.assertEqual(run.location_index, 0)
        self.assertEqual(run.loop_tier, 2)

    def test_defeat_ladder_final_payout(self):
        meta = MetaState()
        run = RunState(seed=1, completed_bosses=2, best_item_value=300)
        logs = []
        for _ in range(4):
            apply_defeat_penalty(random.Random(1), meta, run, logs)
        self.assertFalse(run.active)
        self.assertGreater(meta.gold, 0)

    def test_inventory_full_and_crafting_fusion(self):
        meta = MetaState()
        run = RunState(seed=1)
        rng = random.Random(4)
        items = [roll_item(rng, run, 0, 0, force_quality="trash") for _ in range(12)]
        for item in items:
            self.assertTrue(add_item_to_inventory(meta, run, item)[0])
        self.assertFalse(add_item_to_inventory(meta, run, roll_item(rng, run, 0, 0))[0])
        run.coins = 10000
        ok, message, crafted = craft_fusion(rng, meta, run, items[:3], 0, 0)
        self.assertTrue(ok, message)
        self.assertIsNotNone(crafted)
        self.assertEqual(crafted.quality, "worn")

    def test_save_load_round_trip(self):
        import tempfile
        from pathlib import Path

        data = SaveData(meta=MetaState(gold=12), run=RunState(seed=42, loop_tier=2))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            save_game(data, path)
            loaded = load_game(path)
        self.assertEqual(loaded.meta.gold, 12)
        self.assertEqual(loaded.run.seed, 42)
        self.assertEqual(loaded.run.loop_tier, 2)

    def test_final_gold_payout_increases_with_bosses(self):
        meta = MetaState()
        one = final_gold_payout(meta, RunState(seed=1, completed_bosses=1))
        three = final_gold_payout(meta, RunState(seed=1, completed_bosses=3))
        self.assertGreater(three, one)


if __name__ == "__main__":
    unittest.main()
