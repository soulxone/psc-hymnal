"""Audio backend — pygame.mixer for MIDI, QMediaPlayer for MP3/OGG/WAV."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

MIDI_EXTS = {".mid", ".midi", ".rmi"}


class AudioBackend(QObject):
    state_changed = pyqtSignal(str)  # "playing" | "paused" | "stopped" | "no-audio"
    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._pygame_ready: bool = False
        self._using_pygame: bool = False
        self._current: Optional[Path] = None

        self._qmp = QMediaPlayer(self)
        self._qmp_out = QAudioOutput(self)
        self._qmp.setAudioOutput(self._qmp_out)
        self._qmp.playbackStateChanged.connect(self._on_qmp_state)
        self._qmp.mediaStatusChanged.connect(self._on_qmp_status)

        self._midi_watchdog = QTimer(self)
        self._midi_watchdog.setInterval(500)
        self._midi_watchdog.timeout.connect(self._poll_midi)
        self._midi_was_playing = False

    # ------------------------------------------------------------------ pygame
    def _init_pygame(self) -> bool:
        if self._pygame_ready:
            return True
        try:
            import pygame  # type: ignore
            pygame.mixer.init()
            self._pygame_ready = True
        except Exception as e:
            print(f"[audio] pygame init failed: {e}")
            self._pygame_ready = False
        return self._pygame_ready

    def _poll_midi(self) -> None:
        if not (self._using_pygame and self._pygame_ready):
            return
        try:
            import pygame  # type: ignore
            busy = pygame.mixer.music.get_busy()
        except Exception:
            return
        if self._midi_was_playing and not busy:
            self._midi_was_playing = False
            self._midi_watchdog.stop()
            self.state_changed.emit("stopped")
            self.finished.emit()

    # ------------------------------------------------------------------ public
    def load(self, path: Optional[Path]) -> None:
        self.stop()
        if path is None or not path.exists():
            self._current = None
            self.state_changed.emit("no-audio")
            return
        self._current = path
        if path.suffix.lower() in MIDI_EXTS:
            if not self._init_pygame():
                self._current = None
                self.state_changed.emit("no-audio")
                return
            self._using_pygame = True
            import pygame  # type: ignore
            try:
                pygame.mixer.music.load(str(path))
            except Exception as e:
                print(f"[audio] MIDI load failed: {e}")
                self._current = None
                self.state_changed.emit("no-audio")
                return
        else:
            self._using_pygame = False
            self._qmp.setSource(QUrl.fromLocalFile(str(path)))
        self.state_changed.emit("stopped")

    def play(self) -> None:
        if self._current is None:
            return
        if self._using_pygame:
            import pygame  # type: ignore
            try:
                pygame.mixer.music.play()
                self._midi_was_playing = True
                self._midi_watchdog.start()
                self.state_changed.emit("playing")
            except Exception as e:
                print(f"[audio] MIDI play failed: {e}")
        else:
            self._qmp.play()

    def pause(self) -> None:
        if self._using_pygame:
            import pygame  # type: ignore
            pygame.mixer.music.pause()
            self.state_changed.emit("paused")
        else:
            self._qmp.pause()

    def resume(self) -> None:
        if self._using_pygame:
            import pygame  # type: ignore
            pygame.mixer.music.unpause()
            self.state_changed.emit("playing")
        else:
            self._qmp.play()

    def stop(self) -> None:
        if self._using_pygame and self._pygame_ready:
            import pygame  # type: ignore
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            self._midi_was_playing = False
            self._midi_watchdog.stop()
            self.state_changed.emit("stopped")
        else:
            self._qmp.stop()

    def toggle_play_pause(self) -> None:
        if self._current is None:
            return
        if self._using_pygame:
            import pygame  # type: ignore
            if pygame.mixer.music.get_busy():
                self.pause()
            elif self._midi_was_playing:
                self.resume()
            else:
                self.play()
        else:
            if self._qmp.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._qmp.pause()
            else:
                self._qmp.play()

    def position_ms(self) -> int:
        """Current playback position in milliseconds (0 if stopped)."""
        if self._using_pygame:
            if not self._pygame_ready:
                return 0
            import pygame  # type: ignore
            try:
                p = pygame.mixer.music.get_pos()
                return max(0, p)
            except Exception:
                return 0
        else:
            return int(self._qmp.position())

    def is_playing(self) -> bool:
        if self._using_pygame:
            if not self._pygame_ready:
                return False
            import pygame  # type: ignore
            try:
                return bool(pygame.mixer.music.get_busy())
            except Exception:
                return False
        return self._qmp.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # ----------------------------------------------------------- QMediaPlayer
    def _on_qmp_state(self, state: QMediaPlayer.PlaybackState) -> None:
        if self._using_pygame:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.state_changed.emit("playing")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.state_changed.emit("paused")
        else:
            self.state_changed.emit("stopped")

    def _on_qmp_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if self._using_pygame:
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()
