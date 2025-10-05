from __future__ import annotations
import pygame, pygame_gui
from typing import Protocol

class Screen:
    """Base pour les fenêtres"""
    def _init__(self, app: "AppLike"):
        self.app = app
        self.ui = pygame_gui.UIManager = app.ui
    
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
        self.scene = SceneView(self.ui, area_rect=...)     # zone haute
        self.dialog = DialogPanel(self.ui, area_rect=...)  # zone basse


# =====================================
# Protocol et widgets pour les screens
# =====================================
class AppLike(Protocol):
        ui: pygame_gui.UIManager
        size: tuple[int, int]
        def request_quit(self) -> None: ...

class SceneView:
    """Zone haute : visuels/état (camp, combat, etc.)."""
    def __init__(self, manager: pygame_gui.UIManager, rect: pygame.Rect) -> None:
        self.container = pygame_gui.elements.UIPanel(rect, manager=manager)

    def set_caption(self, text: str) -> None:
        # Exemple très basique : un titre dans la zone
        pygame_gui.elements.UILabel(
            pygame.Rect(self.container.relative_rect.width//2 - 160, 8, 320, 32),
            text, manager=self.container.ui_manager, container=self.container
        )

class DialogPanel:
    """Zone basse : texte + choix cliquables."""
    def __init__(self, manager: pygame_gui.UIManager, rect: pygame.Rect) -> None:
        self.container = pygame_gui.elements.UIPanel(rect, manager=manager)
        self.text_label = pygame_gui.elements.UITextBox(
            html_text="", relative_rect=pygame.Rect(12, 8, rect.width-24, rect.height-80),
            manager=manager, container=self.container
        )
        self.choice_buttons: list[pygame_gui.elements.UIButton] = []
        self._choice_map: dict[pygame_gui.elements.UIButton, int] = {}
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
            btn = pygame_gui.elements.UIButton(
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
            self._last_choice = getattr(event.ui_element, "_veltharia_choice_index", None)
        return self._last_choice

    def take_choice(self) -> int | None:
        """Récupère et consomme le dernier choix (si fait)."""
        c, self._last_choice = self._last_choice, None
        return c
