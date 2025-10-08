from __future__ import annotations
import pygame, pygame_gui
from random import randint

from ui.screens.base import Screen

class MainMenuScreen(Screen):
    def enter(self) -> None:
        super().enter()
        self.app.audio.play_music("01 1 titles INITIAL.mp3")
        w, h = self.app.size
        pygame_gui.elements.UILabel(pygame.Rect(w//2-220, 60, 440, 60),
                                    "Tour de Veltharia",
                                    manager=self.ui)
        for i, txt in enumerate(["Jouer", "Charger", "Réglages", "Quitter"]):
            pygame_gui.elements.UIButton(pygame.Rect(240, (i+1)*108, 480, 80),
                                         txt, manager=self.ui)

    def process_event(self, event: pygame.event.Event) -> None:
        super().process_event(event)
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            t = event.ui_element.text
            if t == "Jouer":
                i = randint(9, 12)
                self.app.audio.play_sfx(f"Minimalist{i}.ogg")
                # self.app.screens.set("character_creation")
                print("Jouer")
                pass
            elif t == "Charger":
                i = randint(9, 12)
                self.app.audio.play_sfx(f"Minimalist{i}.ogg")
                self.app.screens.set("load")
                pass
            elif t == "Réglages":
                i = randint(9, 12)
                self.app.audio.play_sfx(f"Minimalist{i}.ogg")
                self.app.screens.set("settings")
            elif t == "Quitter":
                self.app.audio.play_sfx("Minimalist13.ogg")
                self.app.request_quit()
        elif event.type == pygame_gui.UI_BUTTON_ON_HOVERED:
            i = randint(2, 4)
            self.app.audio.play_sfx(f"Modern{i}.ogg")
