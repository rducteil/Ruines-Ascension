from __future__ import annotations
import pygame, pygame_gui
from pygame_gui.elements import UIButton, UIPanel, UILabel, UITextBox
from typing import Protocol
from pathlib import Path

class Screen:
    """Base pour les fenêtres"""
    def __init__(self, app: "AppLike"):
        self.app = app
        self.ui: pygame_gui.UIManager = app.ui
        self.mx: pygame.mixer = app.mx
    
    def enter(self) -> None:
        self.ui.clear_and_reset()

    def exit(self) -> None:
        pass

    def process_event(self, event: pygame.event.Event) -> None:
        self.ui.process_events(event)

    def update(self, dt: float) -> None:
        self.ui.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((18,18,22))
        self.ui.draw_ui(surface)

class GameScreen(Screen):
    def enter(self) -> None:
        super().enter()
        w, h = self.app.size
        top_h = int(h * 0.6)
        self.scene = SceneView(self.ui, pygame.Rect(0, 0, w, top_h))     # zone haute
        self.dialog = DialogPanel(self.ui, pygame.Rect(0, top_h, w, h - top_h))  # zone basse


# ===============================================
# Protocol et widgets pour les screens et l'audio
# ===============================================
class ScreenManagerLike(Protocol):
    app: AppLike
    _screens: dict[str, Screen]
    current: Screen | None
    mx: pygame.mixer
    def register(self, name: str, screen: Screen) -> None: ...
    def set(self, name: str) -> None: ...

class AudioManagerLike:
    assets_root: Path
    music_vol: float
    sfx_vol: float
    def _music_path(self, name: str) -> str: ...
    def play_music(self, filename: str, *, loop: bool = True, fade_ms: int = 600): ...
    def stop_music(self, fade_ms: int = 400): ...
    def set_music_volume(self, v: float): ...
    def _sfx_path(self, name: str): ...
    def load_sfx(self, filename: str) -> pygame.mixer.Sound: ...
    def play_sfx(self, filename: str): ...
    def set_master(self, v: float): ...
    def quit(self): ...

class AppLike(Protocol):
    ui: pygame_gui.UIManager
    audio: AudioManagerLike
    size: tuple[int, int]
    screens: ScreenManagerLike
    session: dict[str, object]
    def request_quit(self) -> None: ...


class SceneView:
    """Zone haute : visuels/état (camp, combat, etc.)."""
    def __init__(self, manager: pygame_gui.UIManager, rect: pygame.Rect) -> None:
        self.container = UIPanel(rect, manager=manager)

    def set_caption(self, text: str) -> None:
        # Exemple très basique : un titre dans la zone
        UILabel(
            pygame.Rect(self.container.relative_rect.width//2 - 160, 8, 320, 32),
            text, manager=self.container.ui_manager, container=self.container
        )

class DialogPanel:
    """Zone basse : texte + choix cliquables."""
    def __init__(self, manager: pygame_gui.UIManager, rect: pygame.Rect) -> None:
        self.container = UIPanel(rect, manager=manager)
        self.text_label = UITextBox(
            html_text="", relative_rect=pygame.Rect(12, 8, rect.width-24, rect.height-30),
            manager=manager, container=self.container
        )
        self.choice_buttons: list[UIButton] = []
        self._choice_map: dict[UIButton, int] = {}
        self._last_choice: int | None = None

    def show_text(self, text: str) -> None:
        self.text_label.set_text(text)

    def show_choices(self, choices: list[str]) -> None:
        # clear les anciens
        for b in self.choice_buttons: b.kill()
        self.choice_buttons.clear()
        self._choice_map.clear()

        # lay out a la verticale
        y = self.text_label.relative_rect.bottom + 8
        for i, label in enumerate(choices):
            btn = UIButton(
                pygame.Rect(16, y, self.container.relative_rect.width-32, 36),
                label, manager=self.container.ui_manager, container=self.container
            )
            self.choice_buttons.append(btn)
            self._choice_map[btn] = i
            y += 40
        self._last_choice = None

    def handle_event(self, event: pygame.event.Event) -> int | None:
        # à appeler depuis process_event() de l'écran
        if event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element in self.choice_buttons:
            self._last_choice = self._choice_map[event.ui_element]
        return self._last_choice

    def take_choice(self) -> int | None:
        """Récupère et consomme le dernier choix (si fait)."""
        c, self._last_choice = self._last_choice, None
        return c
