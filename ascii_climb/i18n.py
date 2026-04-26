from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS_DIR = ROOT / "translations"
MODS_DIR = ROOT / "mods"


class Translator:
    def __init__(self, language: str = "en", enabled_mods: list[str] | None = None):
        self.language = language
        self.enabled_mods = enabled_mods or []
        self.english = self._load_language("en")
        self.selected = self._load_language(language)
        self.mod_english = self._load_mod_language("en")
        self.mod_selected = self._load_mod_language(language)

    def t(self, key: str, **values) -> str:
        text = (
            self.mod_selected.get(key)
            or self.selected.get(key)
            or self.mod_english.get(key)
            or self.english.get(key)
            or key
        )
        if values:
            try:
                return text.format(**values)
            except (KeyError, ValueError):
                return text
        return text

    def _load_language(self, language: str) -> dict[str, str]:
        path = TRANSLATIONS_DIR / f"{language}.json"
        if not path.exists():
            return {}
        return _read_json(path)

    def _load_mod_language(self, language: str) -> dict[str, str]:
        merged = {}
        for mod_id in self.enabled_mods:
            path = MODS_DIR / mod_id / "translations" / f"{language}.json"
            if path.exists():
                merged.update(_read_json(path))
        return merged


def _read_json(path: Path) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(key): str(value) for key, value in data.items()}
