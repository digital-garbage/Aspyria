from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ascii_climb.models import EnemyTemplate, Location, SetDefinition

ROOT = Path(__file__).resolve().parent.parent
BASE_CONTENT_DIR = ROOT / "content" / "en"
MODS_DIR = ROOT / "mods"

BASE_STATS: dict[str, float] = {}
UPGRADE_BASE_COSTS: dict[str, int] = {}
RARITY_MULTIPLIERS: dict[str, float] = {}
QUALITY_MULTIPLIERS: dict[str, float] = {}
SLOT_STAT_POOLS: dict[str, list[str]] = {}
RARITY_NAMES: dict[str, list[str]] = {}
SLOT_NAMES: dict[str, list[str]] = {}
SETS: dict[str, SetDefinition] = {}
ENEMIES: dict[str, EnemyTemplate] = {}
LOCATIONS: list[Location] = []
ENCOUNTERS: dict[str, dict] = {}
LEVEL_REWARDS: dict[str, dict] = {}
PERKS: dict[str, dict] = {}
RELICS: dict[str, dict] = {}
STORY: dict[str, str] = {}
CONTENT_WARNINGS: list[str] = []
CONTENT_CONFLICTS: list["ContentConflict"] = []
LOADED_MODS: list[str] = []


@dataclass
class ModInfo:
    id: str
    name: str
    author: str = ""
    version: str = ""
    description: str = ""
    path: Path = Path()


@dataclass
class ContentConflict:
    kind: str
    content_id: str
    mods: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.content_id}"


def list_available_mods(mods_dir: Path = MODS_DIR) -> list[ModInfo]:
    if not mods_dir.exists():
        return []
    mods = []
    for directory in sorted(path for path in mods_dir.iterdir() if path.is_dir()):
        manifest = directory / "mod.json"
        if not manifest.exists():
            continue
        try:
            data = _read_json(manifest)
        except ValueError:
            continue
        mod_id = str(data.get("id") or directory.name)
        mods.append(
            ModInfo(
                id=mod_id,
                name=str(data.get("name") or mod_id),
                author=str(data.get("author", "")),
                version=str(data.get("version", "")),
                description=str(data.get("description", "")),
                path=directory,
            )
        )
    return mods


def reload_content(
    enabled_mods: list[str] | None = None,
    mod_choices: dict[str, str] | None = None,
    base_dir: Path = BASE_CONTENT_DIR,
    mods_dir: Path = MODS_DIR,
) -> None:
    enabled_mods = enabled_mods or []
    mod_choices = mod_choices or {}
    builder = _ContentBuilder(mod_choices)
    for path in sorted(base_dir.glob("*.json")):
        builder.apply_file(path, "base", is_mod=False)

    available = {mod.id: mod for mod in list_available_mods(mods_dir)}
    missing_warnings = []
    for mod_id in enabled_mods:
        mod = available.get(mod_id)
        if not mod:
            missing_warnings.append(f"Enabled mod not found: {mod_id}")
            continue
        for path in sorted(mod.path.glob("*.json")):
            if path.name == "mod.json" or path.parent.name == "translations":
                continue
            builder.apply_file(path, mod_id, is_mod=True)

    BASE_STATS.clear()
    BASE_STATS.update({key: float(value) for key, value in builder.base_stats.items()})
    UPGRADE_BASE_COSTS.clear()
    UPGRADE_BASE_COSTS.update({key: int(value) for key, value in builder.upgrade_base_costs.items()})
    RARITY_MULTIPLIERS.clear()
    RARITY_MULTIPLIERS.update({key: float(value) for key, value in builder.rarity_multipliers.items()})
    QUALITY_MULTIPLIERS.clear()
    QUALITY_MULTIPLIERS.update({key: float(value) for key, value in builder.quality_multipliers.items()})
    SLOT_STAT_POOLS.clear()
    SLOT_STAT_POOLS.update({key: list(value) for key, value in builder.slot_stat_pools.items()})
    RARITY_NAMES.clear()
    RARITY_NAMES.update({key: list(value) for key, value in builder.rarity_names.items()})
    SLOT_NAMES.clear()
    SLOT_NAMES.update({key: list(value) for key, value in builder.slot_names.items()})
    SETS.clear()
    SETS.update(builder.sets)
    ENEMIES.clear()
    ENEMIES.update(builder.enemies)
    LOCATIONS.clear()
    LOCATIONS.extend(builder.locations)
    ENCOUNTERS.clear()
    ENCOUNTERS.update(builder.encounters)
    LEVEL_REWARDS.clear()
    LEVEL_REWARDS.update(builder.level_rewards)
    PERKS.clear()
    PERKS.update(builder.perks)
    RELICS.clear()
    RELICS.update(builder.relics)
    STORY.clear()
    STORY.update(builder.story)
    CONTENT_WARNINGS.clear()
    CONTENT_WARNINGS.extend(missing_warnings)
    CONTENT_WARNINGS.extend(builder.warnings)
    CONTENT_CONFLICTS.clear()
    CONTENT_CONFLICTS.extend(builder.conflicts)
    LOADED_MODS.clear()
    LOADED_MODS.extend(enabled_mods)


class _ContentBuilder:
    def __init__(self, mod_choices: dict[str, str]):
        self.mod_choices = mod_choices
        self.base_stats: dict[str, float] = {}
        self.upgrade_base_costs: dict[str, int] = {}
        self.rarity_multipliers: dict[str, float] = {}
        self.quality_multipliers: dict[str, float] = {}
        self.slot_stat_pools: dict[str, list[str]] = {}
        self.rarity_names: dict[str, list[str]] = {}
        self.slot_names: dict[str, list[str]] = {}
        self.sets: dict[str, SetDefinition] = {}
        self.enemies: dict[str, EnemyTemplate] = {}
        self.locations: list[Location] = []
        self.encounters: dict[str, dict] = {}
        self.level_rewards: dict[str, dict] = {}
        self.perks: dict[str, dict] = {}
        self.relics: dict[str, dict] = {}
        self.story: dict[str, str] = {}
        self.sources: dict[str, str] = {}
        self.conflicts: list[ContentConflict] = []
        self.warnings: list[str] = []

    def apply_file(self, path: Path, source_mod: str, is_mod: bool) -> None:
        try:
            data = _read_json(path)
        except ValueError as error:
            self.warnings.append(str(error))
            return
        self._merge_plain("base_stats", self.base_stats, data.get("base_stats", {}), source_mod, is_mod)
        self._merge_plain(
            "upgrade_base_costs",
            self.upgrade_base_costs,
            data.get("upgrade_base_costs", {}),
            source_mod,
            is_mod,
        )
        self._merge_plain(
            "rarity_multipliers",
            self.rarity_multipliers,
            data.get("rarity_multipliers", {}),
            source_mod,
            is_mod,
        )
        self._merge_plain(
            "quality_multipliers",
            self.quality_multipliers,
            data.get("quality_multipliers", {}),
            source_mod,
            is_mod,
        )
        self._merge_plain(
            "slot_stat_pools", self.slot_stat_pools, data.get("slot_stat_pools", {}), source_mod, is_mod
        )
        self._merge_plain("rarity_names", self.rarity_names, data.get("rarity_names", {}), source_mod, is_mod)
        self._merge_plain("slot_names", self.slot_names, data.get("slot_names", {}), source_mod, is_mod)
        for content_id, entry in data.get("sets", {}).items():
            if self._should_apply("set", content_id, source_mod, is_mod):
                self.sets[content_id] = _parse_set(entry, source_mod)
        for content_id, entry in data.get("enemies", {}).items():
            if self._should_apply("enemy", content_id, source_mod, is_mod):
                self.enemies[content_id] = _parse_enemy(entry, source_mod)
        if "locations" in data:
            if is_mod and self.sources.get("locations") not in {None, "base"}:
                self._record_conflict("locations", "route", self.sources["locations"], source_mod)
            if not is_mod or self.sources.get("locations") == "base" or self.mod_choices.get("locations:route") == source_mod:
                self.locations = [_parse_location(entry, source_mod) for entry in data.get("locations", [])]
                self.sources["locations"] = source_mod
        encounters = data.get("encounters", {})
        if isinstance(encounters, list):
            encounters = {entry.get("id", f"encounter_{index}"): entry for index, entry in enumerate(encounters)}
        for content_id, entry in encounters.items():
            if self._should_apply("encounter", content_id, source_mod, is_mod):
                self.encounters[content_id] = dict(entry, source_mod=source_mod)
        for content_id, entry in data.get("level_rewards", {}).items():
            if self._should_apply("level_reward", content_id, source_mod, is_mod):
                self.level_rewards[content_id] = dict(entry, id=content_id, source_mod=source_mod)
        for content_id, entry in data.get("perks", {}).items():
            if self._should_apply("perk", content_id, source_mod, is_mod):
                self.perks[content_id] = dict(entry, id=content_id, source_mod=source_mod)
        for content_id, entry in data.get("relics", {}).items():
            if self._should_apply("relic", content_id, source_mod, is_mod):
                self.relics[content_id] = dict(entry, id=content_id, source_mod=source_mod)
        self._merge_plain("story", self.story, data.get("story", {}), source_mod, is_mod)

    def _merge_plain(
        self,
        kind: str,
        target: dict[str, Any],
        incoming: dict[str, Any],
        source_mod: str,
        is_mod: bool,
    ) -> None:
        for key, value in incoming.items():
            if self._should_apply(kind, key, source_mod, is_mod):
                target[key] = value

    def _should_apply(self, kind: str, content_id: str, source_mod: str, is_mod: bool) -> bool:
        key = f"{kind}:{content_id}"
        current = self.sources.get(key)
        if current and is_mod and current != "base" and current != source_mod:
            self._record_conflict(kind, content_id, current, source_mod)
            if self.mod_choices.get(key) == source_mod:
                self.sources[key] = source_mod
                return True
            return False
        self.sources[key] = source_mod
        return True

    def _record_conflict(self, kind: str, content_id: str, first_mod: str, second_mod: str) -> None:
        key = f"{kind}:{content_id}"
        for conflict in self.conflicts:
            if conflict.key == key:
                for mod in (first_mod, second_mod):
                    if mod not in conflict.mods:
                        conflict.mods.append(mod)
                return
        self.conflicts.append(ContentConflict(kind=kind, content_id=content_id, mods=[first_mod, second_mod]))


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not load {path}: {error}") from error


def _parse_set(data: dict, source_mod: str) -> SetDefinition:
    return SetDefinition(
        name=str(data["name"]),
        required_slots=list(data["required_slots"]),
        partial_stat=str(data["partial_stat"]),
        partial_bonus=float(data["partial_bonus"]),
        full_bonuses={key: float(value) for key, value in data.get("full_bonuses", {}).items()},
        drawback=str(data.get("drawback", "")),
        source_mod=source_mod,
    )


def _parse_enemy(data: dict, source_mod: str) -> EnemyTemplate:
    return EnemyTemplate(
        name=str(data["name"]),
        family=str(data["family"]),
        base_hp=int(data["base_hp"]),
        base_atk=int(data["base_atk"]),
        xp=int(data["xp"]),
        coins=int(data["coins"]),
        abilities=list(data.get("abilities", [])),
        boss=bool(data.get("boss", False)),
        corrupted=bool(data.get("corrupted", False)),
        source_mod=source_mod,
        multi_attack_chance=float(data.get("multi_attack_chance", 0.0)),
        evasion_chance=float(data.get("evasion_chance", 0.0)),
        dialogue={key: str(value) for key, value in data.get("dialogue", {}).items()},
    )


def _parse_location(data: dict, source_mod: str) -> Location:
    return Location(
        name=str(data["name"]),
        min_ilevel=int(data.get("min_ilevel", data.get("ilevel_threshold", 1))),
        max_ilevel=int(data.get("max_ilevel", data.get("ilevel_threshold", 1) + 4)),
        difficulty=float(data["difficulty"]),
        fights_to_boss=int(data["fights_to_boss"]),
        enemy_names=list(data["enemy_names"]),
        boss_name=str(data["boss_name"]),
        source_mod=source_mod,
        story={key: str(value) for key, value in data.get("story", {}).items()},
    )


reload_content()
