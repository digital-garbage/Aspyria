from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from ascii_climb.models import GameSettings, SaveData
from ascii_climb.state import sanitize_run_state

SAVE_PATH = Path("savegame.json")
SAVES_DIR = Path("saves")
SETTINGS_PATH = Path("settings.json")
LEGACY_IMPORT_MARKER = SAVES_DIR / ".legacy_imported"


def load_game(path: Path = SAVE_PATH) -> SaveData:
    if not path.exists():
        return SaveData()
    with path.open("r", encoding="utf-8") as handle:
        return SaveData.from_dict(json.load(handle))


def save_game(data: SaveData, path: Path = SAVE_PATH) -> None:
    sanitize_run_state(data.run)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data.to_dict(), handle, indent=2, sort_keys=True)


@dataclass
class SaveSlotSummary:
    slot_id: str
    name: str
    path: Path
    has_run: bool
    gold: int
    play_time_seconds: float
    last_played_at: float
    required_mods: list[str]


def load_settings(path: Path = SETTINGS_PATH) -> GameSettings:
    if not path.exists():
        return GameSettings()
    with path.open("r", encoding="utf-8") as handle:
        return GameSettings.from_dict(json.load(handle))


def save_settings(settings: GameSettings, path: Path = SETTINGS_PATH) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(settings.to_dict(), handle, indent=2, sort_keys=True)


def ensure_save_dir(save_dir: Path = SAVES_DIR) -> None:
    save_dir.mkdir(parents=True, exist_ok=True)


def slot_id_for_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return slug or "save"


def slot_path(slot_id: str, save_dir: Path = SAVES_DIR) -> Path:
    return save_dir / f"{slot_id}.json"


def create_save_slot(name: str, data: SaveData | None = None, save_dir: Path = SAVES_DIR) -> str:
    ensure_save_dir(save_dir)
    base = slot_id_for_name(name)
    slot_id = base
    index = 2
    while slot_path(slot_id, save_dir).exists():
        slot_id = f"{base}-{index}"
        index += 1
    data = data or SaveData()
    sanitize_run_state(data.run)
    data.last_played_at = time.time()
    payload = {"slot_id": slot_id, "name": name.strip() or slot_id, "save": data.to_dict()}
    _write_json(slot_path(slot_id, save_dir), payload)
    return slot_id


def list_save_slots(save_dir: Path = SAVES_DIR) -> list[SaveSlotSummary]:
    ensure_save_dir(save_dir)
    import_legacy_save(save_dir=save_dir)
    summaries = []
    for path in sorted(save_dir.glob("*.json")):
        try:
            payload = _read_json(path)
            data = SaveData.from_dict(payload.get("save", payload))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        summaries.append(
            SaveSlotSummary(
                slot_id=payload.get("slot_id", path.stem),
                name=payload.get("name", path.stem),
                path=path,
                has_run=data.run is not None,
                gold=data.meta.gold,
                play_time_seconds=data.stats.play_time_seconds,
                last_played_at=data.last_played_at,
                required_mods=data.required_mods,
            )
        )
    return sorted(summaries, key=lambda item: item.last_played_at, reverse=True)


def load_save_slot(slot_id: str, save_dir: Path = SAVES_DIR) -> SaveData:
    payload = _read_json(slot_path(slot_id, save_dir))
    return SaveData.from_dict(payload.get("save", payload))


def save_save_slot(slot_id: str, name: str, data: SaveData, save_dir: Path = SAVES_DIR) -> None:
    ensure_save_dir(save_dir)
    sanitize_run_state(data.run)
    data.last_played_at = time.time()
    payload = {"slot_id": slot_id, "name": name, "save": data.to_dict()}
    _write_json(slot_path(slot_id, save_dir), payload)


def rename_save_slot(slot_id: str, new_name: str, save_dir: Path = SAVES_DIR) -> None:
    path = slot_path(slot_id, save_dir)
    payload = _read_json(path)
    payload["name"] = new_name.strip() or slot_id
    _write_json(path, payload)


def delete_save_slot(slot_id: str, save_dir: Path = SAVES_DIR) -> None:
    path = slot_path(slot_id, save_dir)
    if path.exists():
        path.unlink()


def import_legacy_save(
    legacy_path: Path = SAVE_PATH,
    save_dir: Path = SAVES_DIR,
    marker_path: Path | None = None,
) -> str | None:
    ensure_save_dir(save_dir)
    marker_path = marker_path or (save_dir / ".legacy_imported")
    if marker_path.exists() or not legacy_path.exists():
        return None
    data = load_game(legacy_path)
    slot_id = create_save_slot("Imported Save", data, save_dir)
    marker_path.write_text(slot_id, encoding="utf-8")
    return slot_id


def missing_mods_for_save(data: SaveData, enabled_mods: list[str]) -> list[str]:
    return [mod for mod in data.required_mods if mod and mod not in enabled_mods]


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
