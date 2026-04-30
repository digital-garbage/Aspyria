import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ascii_climb import content
from ascii_climb.i18n import Translator
from ascii_climb.encounters import apply_encounter, random_event
from ascii_climb.models import GameSettings, Item, LifetimeStats, MetaState, RunState, SaveData
from ascii_climb.save import (
    create_save_slot,
    delete_save_slot,
    import_legacy_save,
    list_save_slots,
    load_profile,
    load_save_slot,
    load_settings,
    rename_save_slot,
    save_game,
    save_save_slot,
    save_settings,
)
from ascii_climb.stats import record_failed_run, record_item_collected, record_successful_run


class SaveSlotTests(unittest.TestCase):
    def test_create_load_rename_delete_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            save_dir = Path(directory)
            data = SaveData()
            data.meta.gold = 77
            slot_id = create_save_slot("My Save", data, save_dir)
            loaded = load_save_slot(slot_id, save_dir)
            self.assertEqual(loaded.meta.gold, 77)

            rename_save_slot(slot_id, "Better Save", save_dir)
            summaries = list_save_slots(save_dir)
            self.assertEqual(summaries[0].name, "Better Save")

            loaded.meta.gold = 99
            save_save_slot(slot_id, "Better Save", loaded, save_dir)
            self.assertEqual(load_save_slot(slot_id, save_dir).meta.gold, 99)
            payload = json.loads((save_dir / f"{slot_id}.json").read_text(encoding="utf-8"))
            self.assertNotIn("meta", payload["save"])
            self.assertEqual(load_profile(save_dir / "profile.json").gold, 99)

            delete_save_slot(slot_id, save_dir)
            self.assertEqual(list_save_slots(save_dir), [])

    def test_save_sanitizes_invalid_stat_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            save_dir = Path(directory)
            data = SaveData(run=RunState())
            data.run.run_buffs[None] = 5
            data.run.run_debuffs["NOPE"] = 7
            data.run.locked_stats = ["ATK", "NOPE"]
            slot_id = create_save_slot("Bad Stats", data, save_dir)
            loaded = load_save_slot(slot_id, save_dir)
            self.assertNotIn(None, loaded.run.run_buffs)
            self.assertNotIn("NOPE", loaded.run.run_debuffs)
            self.assertEqual(loaded.run.locked_stats, ["ATK"])

    def test_import_legacy_save_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_path = root / "savegame.json"
            save_dir = root / "saves"
            legacy = SaveData()
            legacy.meta.gold = 12
            save_game(legacy, legacy_path)

            slot_id = import_legacy_save(legacy_path=legacy_path, save_dir=save_dir)
            self.assertIsNotNone(slot_id)
            self.assertEqual(load_save_slot(slot_id, save_dir).meta.gold, 12)
            self.assertIsNone(import_legacy_save(legacy_path=legacy_path, save_dir=save_dir))

    def test_split_settings_volume_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(GameSettings(sfx_volume=22, music_volume=44), path)
            loaded = load_settings(path)
        self.assertEqual(loaded.sfx_volume, 22)
        self.assertEqual(loaded.music_volume, 44)


class LifetimeStatsTests(unittest.TestCase):
    def test_item_codex_and_run_records(self):
        stats = LifetimeStats()
        item = Item("1", "Grand Knife", "weapon", "rare", "used", 4, {"ATK": 4}, value=100)
        record_item_collected(stats, item)
        record_item_collected(stats, item)
        self.assertEqual(stats.item_codex["Grand Knife"].count, 2)
        self.assertEqual(stats.rarest_items[0]["name"], "Grand Knife")

        run = RunState(seed=10, started_at=100.0, completed_bosses=2)
        record_failed_run(stats, run, now=160.0)
        self.assertEqual(stats.quickest_failed_run.duration_seconds, 60.0)

        run.loop_tier = 2
        record_successful_run(stats, run, now=220.0)
        self.assertEqual(stats.quickest_successful_run.duration_seconds, 120.0)


class ContentRegistryTests(unittest.TestCase):
    def test_base_mod_override_and_conflict_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_dir = root / "content"
            mods_dir = root / "mods"
            base_dir.mkdir()
            self._write_content(base_dir / "base.json", enemy_hp=10)
            self._write_mod(mods_dir, "mod_one", enemy_hp=20)
            self._write_mod(mods_dir, "mod_two", enemy_hp=30)

            try:
                content.reload_content(["mod_one"], {}, base_dir, mods_dir)
                self.assertEqual(content.ENEMIES["Test Enemy"].base_hp, 20)
                self.assertEqual(content.CONTENT_CONFLICTS, [])

                content.reload_content(["mod_one", "mod_two"], {}, base_dir, mods_dir)
                self.assertEqual(content.ENEMIES["Test Enemy"].base_hp, 20)
                self.assertTrue(
                    any(conflict.content_id == "Test Enemy" for conflict in content.CONTENT_CONFLICTS)
                )

                content.reload_content(
                    ["mod_one", "mod_two"],
                    {"enemy:Test Enemy": "mod_two"},
                    base_dir,
                    mods_dir,
                )
                self.assertEqual(content.ENEMIES["Test Enemy"].base_hp, 30)
            finally:
                content.reload_content()

    def _write_content(self, path: Path, enemy_hp: int) -> None:
        payload = {
            "base_stats": {"ATK": 12, "HP": 100},
            "upgrade_base_costs": {"ATK": 4, "HP": 4},
            "rarity_multipliers": {"common": 1},
            "quality_multipliers": {"used": 1},
            "slot_stat_pools": {"weapon": ["ATK"]},
            "rarity_names": {"common": ["Plain"]},
            "slot_names": {"weapon": ["Knife"]},
            "sets": {},
            "enemies": {
                "Test Enemy": {
                    "name": "Test Enemy",
                    "family": "Tests",
                    "base_hp": enemy_hp,
                    "base_atk": 1,
                    "xp": 1,
                    "coins": 1,
                    "abilities": [],
                }
            },
            "locations": [],
            "encounters": {},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_mod(self, mods_dir: Path, mod_id: str, enemy_hp: int) -> None:
        mod_dir = mods_dir / mod_id
        mod_dir.mkdir(parents=True)
        (mod_dir / "mod.json").write_text(
            json.dumps({"id": mod_id, "name": mod_id, "version": "1.0"}),
            encoding="utf-8",
        )
        self._write_content(mod_dir / "content.json", enemy_hp)


class EncounterTests(unittest.TestCase):
    def test_builtin_encounter_effects_apply(self):
        data = SaveData(run=RunState(seed=5))
        encounter = {
            "title": "Test Cache",
            "effects": [
                {"type": "message", "text": "A cache opens."},
                {"type": "reward_coins", "amount": 7},
                {"type": "reward_gold", "amount": 3},
                {"type": "stat_buff", "stat": "ATK", "amount": 2},
                {"type": "stat_debuff", "stat": "HP", "amount": 1},
                {
                    "type": "choice_list",
                    "choices": [
                        {"label": "Take spark", "effects": [{"type": "stat_buff", "stat": "Luck%", "amount": 4}]}
                    ],
                },
            ],
        }
        result = apply_encounter(random.Random(1), data.meta, data.run, encounter)
        self.assertIn("A cache opens.", result.logs)
        self.assertEqual(data.run.coins, 7)
        self.assertEqual(data.meta.gold, 3)
        self.assertEqual(data.run.run_buffs["ATK"], 2)
        self.assertEqual(data.run.run_buffs["Luck%"], 4)
        self.assertEqual(data.run.run_debuffs["HP"], 1)

    def test_bandit_fight_can_cause_defeat(self):
        run = RunState(seed=8, coins=100, current_hp=3)
        encounter = {
            "title": "Bandit's Toll",
            "body": "A bandit blocks your way.",
            "handler": "bandit_toll",
            "params": {"toll_fraction": 0.9, "legendary_chance": 0.0},
            "choices": [{"id": "pay", "label": "Pay"}, {"id": "fight", "label": "Fight him"}],
        }
        result = random_event(random.Random(0), MetaState(), run, event=encounter, choice_index=1)
        self.assertIsNotNone(result)
        self.assertEqual(run.defeats, 1)
        self.assertIn("defeats you", "\n".join(result.logs))
        self.assertLess(run.coins, 100)


class TranslationTests(unittest.TestCase):
    def test_russian_keys_match_english_and_fallback_works(self):
        root = Path(__file__).resolve().parent.parent
        en = json.loads((root / "translations" / "en.json").read_text(encoding="utf-8"))
        ru = json.loads((root / "translations" / "ru.json").read_text(encoding="utf-8"))
        self.assertEqual(set(en), set(ru))
        self.assertEqual(Translator("missing-language").t("menu.new_run"), "New Run")
        self.assertEqual(Translator("ru").t("content.optional.name"), "content.optional.name")


class DocumentationTests(unittest.TestCase):
    def test_license_and_commercial_docs_are_referenced(self):
        root = Path(__file__).resolve().parent.parent
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("LICENSE.md", readme)
        self.assertIn("COMMERCIAL_USE.md", readme)
        self.assertIn("Grok Imagine", readme)
        self.assertIn("Kenney", readme)
        self.assertTrue((root / "assets" / "sounds" / "click.wav").exists())


class QtSmokeTests(unittest.TestCase):
    def test_main_menu_and_resolution_smoke(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtCore import QPoint
        from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
        from ascii_climb.combat import run_combat
        from ascii_climb.models import MetaState
        from ascii_climb.qt_app import AspyriaWindow, FightReplayDialog, make_sprite_pixmap

        app = QApplication.instance() or QApplication([])
        window = AspyriaWindow()
        window.show()
        self.assertEqual(window.stack.currentWidget(), window.disclaimer_page)
        window.show_menu()
        self.assertEqual(window.stack.currentWidget(), window.menu_page)
        self.assertEqual(window.sound.current_music_key, "menu")
        menu_buttons = window.menu_page.findChildren(QPushButton)
        self.assertTrue(menu_buttons)
        window.sound.last_effect_key = ""
        menu_buttons[0].click()
        self.assertEqual(window.sound.last_effect_key, "click")
        window.show_credits()
        self.assertEqual(window.stack.currentWidget(), window.credits_page)
        labels = [label.text() for label in window.credits_page.findChildren(QLabel)]
        self.assertTrue(any("Aspyria is brought to you by:" in text for text in labels))
        self.assertTrue(any("Tiny5 by Stefan Schmidt" in text for text in labels))
        self.assertTrue(any("Pixelify Sans by Stefie Justprince" in text for text in labels))
        self.assertEqual(menu_buttons[0].parentWidget().maximumWidth(), window.menu_logo_width)
        run = RunState(seed=1)
        run.run_buffs["ATK"] = 1000
        result = run_combat(random.Random(2), MetaState(), run)
        dialog = FightReplayDialog(result, make_sprite_pixmap("player"), make_sprite_pixmap("enemy"), window)
        self.assertTrue(dialog.events)
        dialog.close()
        fleeing_run = RunState(seed=2)
        fleeing_dialog = FightReplayDialog(
            None,
            make_sprite_pixmap("player"),
            make_sprite_pixmap("enemy"),
            window,
            rng=random.Random(2),
            meta=MetaState(),
            run=fleeing_run,
        )
        fleeing_dialog.reject()
        self.assertTrue(fleeing_dialog.result.fled)
        live_dialog = FightReplayDialog(
            None,
            make_sprite_pixmap("player"),
            make_sprite_pixmap("enemy"),
            window,
            rng=random.Random(2),
            meta=MetaState(),
            run=RunState(seed=3),
        )
        live_dialog.stance_combo.setCurrentText("reckless")
        self.assertIn("Reckless", live_dialog.action.text())
        live_dialog.close()
        gear = Item("drag-weapon", "Drag Blade", "weapon", "common", "used", 1, {"ATK": 2}, value=1)
        window.data = SaveData(run=RunState(seed=4, inventory=[gear]))
        window.refresh_all()
        self.assertTrue(window.handle_slot_drop("inventory|0|drag-weapon|", window.equipment_slots["weapon"]))
        self.assertEqual(window.data.run.equipment["weapon"].id, "drag-weapon")
        self.assertEqual(window.data.run.inventory, [])
        self.assertTrue(window.handle_inventory_table_drop("equipment|-1|drag-weapon|weapon", 0))
        self.assertIsNone(window.data.run.equipment["weapon"])
        self.assertEqual(window.data.run.inventory[0].id, "drag-weapon")
        second = Item("drag-armor", "Drag Plate", "armor", "rare", "used", 1, {"HP": 5}, value=12)
        window.data.run.inventory.append(second)
        window.refresh_all()
        self.assertTrue(window.handle_inventory_table_drop("inventory|0|drag-weapon|", 1))
        self.assertEqual([item.id for item in window.data.run.inventory], ["drag-armor", "drag-weapon"])
        with patch("ascii_climb.qt_app.QMessageBox.information"):
            self.assertFalse(window.handle_slot_drop("inventory|0|drag-armor|", window.equipment_slots["weapon"]))
        self.assertIsNone(window.data.run.equipment["weapon"])
        window.inventory_table.selectRow(0)
        self.assertFalse(window.inventory_sell_button.isHidden())
        window.equipment_slots["weapon"].drag_start = QPoint(0, 0)
        self.assertFalse(window.equipment_slots["weapon"].drag_distance_reached(QPoint(1, 1)))
        self.assertTrue(window.equipment_slots["weapon"].drag_distance_reached(QPoint(QApplication.startDragDistance(), 0)))
        hp_gear = Item("hp-gear", "Vital Blade", "weapon", "common", "used", 1, {"HP": 10}, value=20)
        window.data.run.equipment["weapon"] = hp_gear
        window.data.run.current_hp = 25
        coins_before = window.data.run.coins
        window.refresh_all()
        window.slot_clicked(window.equipment_slots["weapon"])
        self.assertFalse(window.equipment_slots["weapon"].sell_button.isHidden())
        window.sell_slot_item(window.equipment_slots["weapon"])
        self.assertIsNone(window.data.run.equipment["weapon"])
        self.assertGreater(window.data.run.coins, coins_before)
        self.assertLessEqual(window.data.run.current_hp, 15)
        window.selected_inventory_ids = {window.data.run.inventory[0].id}
        window.refresh_shop_tab()
        window.refresh_inventory_action_buttons()
        self.assertIn("coins", window.shop_inventory_improve_button.text())
        self.assertIn("coins", window.buy_random_button.text())
        self.assertIn("coins", window.medkit_buttons["small"].text())
        self.assertNotIn("Luck:", window.shop_status.text())
        self.assertNotIn("Enemy Scaling", window.shop_status.text())
        self.assertNotIn("Medkits:", window.shop_status.text())
        window.refresh_game_page()
        self.assertIn("coins", window.scout_button.text())
        self.assertTrue(window.stats_table.hasMouseTracking())
        self.assertTrue(window.stats_table.viewport().hasMouseTracking())
        luck_description = next(
            window.stats_table.item(row, 2).toolTip()
            for row in range(window.stats_table.rowCount())
            if window.stats_table.item(row, 0).text() == "Luck%"
        )
        self.assertIn("higher item rarity", luck_description)
        window.settings.resolution = "1366x768"
        window.settings.fullscreen = False
        window.apply_resolution()
        self.assertGreaterEqual(window.width(), 1000)
        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
