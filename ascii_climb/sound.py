from __future__ import annotations

import os
from pathlib import Path

try:
    from PyQt6.QtCore import QCoreApplication, QUrl
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect
except ModuleNotFoundError:
    try:
        from PyQt5.QtCore import QCoreApplication, QUrl
        from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QSoundEffect
        QAudioOutput = None
    except ModuleNotFoundError:
        QCoreApplication = None
        QSoundEffect = None
        QUrl = None
        QMediaPlayer = None
        QAudioOutput = None
        QMediaContent = None


SOUND_FILES = {
    "click": "click.wav",
    "attack": "attack.wav",
    "dodge": "dodge.wav",
    "coin": "coin.wav",
    "loot": "loot.wav",
    "victory": "victory.wav",
    "defeat": "defeat.wav",
    "level": "level.wav",
    "error": "error.wav",
    "event": "event.wav",
}

MUSIC_FILES = {
    "menu": "menu.mp3",
    "idle": "idle.mp3",
    "regular_fight": "regular_fight.mp3",
    "bossfight": "bossfight.mp3",
}


class SoundManager:
    def __init__(
        self,
        root: Path,
        sfx_volume: int = 70,
        music_root: Path | None = None,
        music_volume: int | None = None,
    ):
        self.root = root
        self.music_root = music_root or root
        has_app = QCoreApplication is not None and QCoreApplication.instance() is not None
        self.enabled = (
            has_app
            and
            QSoundEffect is not None
            and QUrl is not None
            and os.environ.get("QT_QPA_PLATFORM") != "offscreen"
        )
        self.music_enabled = (
            has_app
            and
            QMediaPlayer is not None
            and QUrl is not None
            and os.environ.get("QT_QPA_PLATFORM") != "offscreen"
        )
        self.effects = {}
        self.sfx_volume = 0.0
        self.music_volume = 0.0
        self.last_effect_key = ""
        self.current_music_key = ""
        self._music_url = None
        self.player = None
        self.audio_output = None
        if self.enabled:
            for key, filename in SOUND_FILES.items():
                path = root / filename
                if not path.exists():
                    continue
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path)))
                self.effects[key] = effect
        if self.music_enabled:
            self.player = QMediaPlayer()
            if QAudioOutput is not None:
                self.audio_output = QAudioOutput()
                self.player.setAudioOutput(self.audio_output)
            self._connect_music_loop()
        self.set_sfx_volume(sfx_volume)
        self.set_music_volume(sfx_volume if music_volume is None else music_volume)

    def set_volume(self, volume: int) -> None:
        self.set_sfx_volume(volume)
        self.set_music_volume(volume)

    def set_sfx_volume(self, volume: int) -> None:
        self.sfx_volume = max(0.0, min(1.0, volume / 100.0))
        for effect in self.effects.values():
            effect.setVolume(self.sfx_volume)

    def set_music_volume(self, volume: int) -> None:
        self.music_volume = max(0.0, min(1.0, volume / 100.0))
        if self.audio_output is not None:
            self.audio_output.setVolume(self.music_volume)
        elif self.player is not None and hasattr(self.player, "setVolume"):
            self.player.setVolume(int(self.music_volume * 100))

    def play(self, key: str) -> None:
        self.last_effect_key = key
        effect = self.effects.get(key)
        if effect is not None and self.sfx_volume > 0:
            effect.play()

    def set_music(self, key: str | None) -> None:
        target = key or ""
        if target == self.current_music_key:
            return
        self.current_music_key = target
        if self.player is None:
            return
        if not target:
            self.player.stop()
            self._music_url = None
            return
        filename = MUSIC_FILES.get(target)
        if not filename:
            return
        path = self.music_root / filename
        if not path.exists():
            self.player.stop()
            self._music_url = None
            return
        self._music_url = QUrl.fromLocalFile(str(path))
        if QAudioOutput is not None:
            self.player.setSource(self._music_url)
        else:
            self.player.setMedia(QMediaContent(self._music_url))
        self.player.play()

    def _connect_music_loop(self) -> None:
        if self.player is None:
            return
        signal = getattr(self.player, "mediaStatusChanged", None)
        if signal is not None:
            signal.connect(self._restart_music_if_needed)

    def _restart_music_if_needed(self, status) -> None:
        if self.player is None or not self.current_music_key or self._music_url is None:
            return
        end_status = (
            QMediaPlayer.MediaStatus.EndOfMedia
            if hasattr(QMediaPlayer, "MediaStatus")
            else QMediaPlayer.EndOfMedia
        )
        if status != end_status:
            return
        if QAudioOutput is not None:
            self.player.setSource(self._music_url)
        else:
            self.player.setMedia(QMediaContent(self._music_url))
        self.player.play()
