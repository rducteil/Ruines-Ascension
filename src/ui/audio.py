from __future__ import annotations
from pathlib import Path
import pygame

class AudioManager:
    """Charge, met en cache et joue musique & SFX. Gère les volumes par catégories"""
    def __init__(self, assets_root: Path, music_vol: float = 0.6, sfx_vol: float = 0.8):
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.assets = assets_root
        self._cache_sfx: dict[str, pygame.mixer.Sound] = {}
        self._music_current: str | None = None

        self.master = 1.0
        self.music_vol = music_vol
        self.sfx_vol = sfx_vol
    
    # --- Music ---
    def _music_path(self, name: str) -> str:
        return str(self.assets / "sounds" / "Infinity Crystal_ Awakening" / name)
    
    def play_music(self, filename: str, *, loop: bool = True, fade_ms: int = 600):
        path = self._music_path(filename)
        if self._music_current == path:
            return
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(self.master * self.music_vol)
        pygame.mixer.music.play(loops=-1 if loop else 0, fade_ms=fade_ms)
        self._music_current = path

    def stop_music(self, fade_ms: int = 400):
        pygame.mixer.music.fadeout(fade_ms)
        self._music_current = None

    def set_music_volume(self, v: float):
        self.music_vol = max(0.0, min(1.0, v))
        pygame.mixer.music.set_volume(self.master * self.music_vol)
    
    # --- SFX ---
    def _sfx_path(self, name: str):
        return str(self.assets / "sounds" / "UI Soundpack" / "OGG" / name)

    def load_sfx(self, filename: str) -> pygame.mixer.Sound:
        key = filename
        snd = self._cache_sfx.get(key)
        if snd is None:
            snd = pygame.mixer.Sound(self._sfx_path(filename))
            snd.set_volume(self.master * self.sfx_vol)
            self._cache_sfx[key] = snd
        return snd

    def play_sfx(self, filename: str):
        snd = self.load_sfx(filename)
        snd.set_volume(self.master * self.sfx_vol)
        snd.play()

    # --- Global ---
    def set_master(self, v: float):
        self.master = max(0.0, min(1.0, v))
        pygame.mixer.music.set_volume(self.master * self.music_vol)
        for snd in self._cache_sfx.values():
            snd.set_volume(self.master * self.sfx_vol)

    def quit(self):
        pygame.mixer.music.stop()