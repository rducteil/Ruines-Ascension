from __future__ import annotations
import pygame, pygame_gui
from random import randint

from ui.screens.base import Screen

class LoadScreen(Screen):
    def enter(self) -> None:
        super().enter()
        w, h = self.app.size
        pygame_gui.elements.UILabel(pygame.Rect(w//2-220, 60, 440, 60),
                                    "Charger",
                                    manager=self.ui)
        for i, txt in enumerate(["Fichier 1", "Fichier 2", "Fichier 3", "Quitter"]):
            pygame_gui.elements.UIButton(pygame.Rect(240, (i+1)*108, 480, 80),
                                         txt, manager=self.ui)

    def process_event(self, event: pygame.event.Event) -> None:
        super().process_event(event)
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            t = event.ui_element.text
            if t == "Quitter":
                self.app.audio.play_sfx("Minimalist13.ogg")
                self.app.screens.set("main_menu")
                pass
            else:
                i = randint(9, 12)
                self.app.audio.play_sfx(f"Minimalist{i}.ogg")
                print(t, " est vide")
        elif event.type == pygame_gui.UI_BUTTON_ON_HOVERED:
            i = randint(2, 4)
            self.app.audio.play_sfx(f"Modern{i}.ogg")
