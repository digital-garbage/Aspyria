import json
import os
import random
import tempfile
import unittest
from pathlib import Path

from ascii_climb import content
from ascii_climb.i18n import Translator
from ascii_climb.encounters import apply_encounter
from ascii_climb.models import Item, LifetimeStats, RunState, SaveData
from ascii_climb.save import (
    create_save_slot,
    delete_save_slot,
    import_legacy_save,
    list_save_slots,
    load_save_slot,
    rename_save_slot,
    save_game,
    save_save_slot,
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
        from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
        from ascii_climb.combat import run_combat
        from ascii_climb.models import MetaState
        from ascii_climb.qt_app import AspyriaWindow, FightReplayDialog, make_sprite_pixmap

        app = QApplication.instance() or QApplication([])
        window = AspyriaWindow()
        window.show()
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
        window.settings.resolution = "1366x768"
        window.settings.fullscreen = False
        window.apply_resolution()
        self.assertGreaterEqual(window.width(), 1000)
        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
