"""
Garlic Phone — Sound Manager
Uses pygame.mixer for cross-platform audio.
"""

import os
import logging

log = logging.getLogger(__name__)

from app.paths import asset

def _sound_path(f): return asset("sounds", f)
def _music_path(f): return asset("music",  f)


class SoundManager:
    def __init__(self, volume: float = 0.7, music_volume: float = 0.2):
        self._enabled       = True
        self._volume        = volume
        self._music_volume  = music_volume
        self._sounds        = {}
        self._current_track = None

        try:
            import pygame
            pygame.mixer.init()
            self._pygame = pygame
            self._load_sounds()
            log.info("SoundManager initialised")
        except ImportError:
            log.warning("pygame not installed — run: pip install pygame")
            self._pygame = None
        except Exception as e:
            log.warning(f"SoundManager failed to init: {e}")
            self._pygame = None

    def _load_sounds(self):
        files = {
            "click":      ["click.mp3",      "click.wav"],
            "join":       ["join.mp3",        "join.wav"],
            "start":      ["start.mp3",       "start.wav"],
            "disconnect": ["disconnect.mp3",  "disconnect.wav"],
            "submit":     ["submit.mp3",      "submit.wav"],
            "results":    ["results.mp3",     "results.wav"],
        }
        for key, candidates in files.items():
            for filename in candidates:
                path = _sound_path(filename)
                if os.path.exists(path):
                    try:
                        sound = self._pygame.mixer.Sound(path)
                        sound.set_volume(self._volume)
                        self._sounds[key] = sound
                        break
                    except Exception as e:
                        log.warning(f"Could not load '{filename}': {e}")

    # ── SFX ───────────────────────────────────────────────────────────────────

    def _play(self, key: str):
        if not self._enabled or self._pygame is None:
            return
        sound = self._sounds.get(key)
        if sound:
            try:
                sound.play()
            except Exception as e:
                log.warning(f"Could not play '{key}': {e}")

    def play_click(self):      self._play("click")
    def play_join(self):       self._play("join")
    def play_start(self):      self._play("start")
    def play_disconnect(self): self._play("disconnect")
    def play_submit(self):     self._play("submit")
    def play_results(self):    self._play("results")

    # ── Music (looping background tracks) ─────────────────────────────────────

    def _play_music(self, filename: str):
        if self._pygame is None:
            return
        if self._current_track == filename:
            return   # already playing — don't restart
        path = _music_path(filename)
        if not os.path.exists(path):
            log.warning(f"Music not found: {path}")
            return
        try:
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.set_volume(self._music_volume)
            self._pygame.mixer.music.play(loops=-1, fade_ms=1000)
            self._current_track = filename
            log.info(f"Music: {filename}")
        except Exception as e:
            log.warning(f"Could not play music '{filename}': {e}")

    def play_music_home(self):
        """Loop home1 on Home / Create / Join screens."""
        for ext in ("home1.mp3", "home1.wav", "home1.ogg"):
            if os.path.exists(_music_path(ext)):
                self._play_music(ext)
                return

    def play_music_lobby(self):
        """Loop lobby1 when inside a lobby."""
        for ext in ("lobby1.mp3", "lobby1.wav", "lobby1.ogg"):
            if os.path.exists(_music_path(ext)):
                self._play_music(ext)
                return

    def stop_music(self, fade_ms: int = 800):
        if self._pygame is None:
            return
        try:
            self._pygame.mixer.music.fadeout(fade_ms)
            self._current_track = None
        except Exception as e:
            log.warning(f"Could not stop music: {e}")

    def set_music_volume(self, volume: float):
        self._music_volume = max(0.0, min(1.0, volume))
        if self._pygame:
            try:
                self._pygame.mixer.music.set_volume(self._music_volume)
            except Exception:
                pass

    # ── Volume / mute ──────────────────────────────────────────────────────────

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))
        for sound in self._sounds.values():
            sound.set_volume(self._volume)

    def set_muted(self, muted: bool):
        self._enabled = not muted

    def is_muted(self) -> bool:
        return not self._enabled

    def toggle_mute(self) -> bool:
        self._enabled = not self._enabled
        return not self._enabled