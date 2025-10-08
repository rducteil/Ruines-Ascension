from __future__ import annotations
import pygame, pygame_gui
from random import randint
from pygame_gui.elements.ui_horizontal_slider import UIHorizontalSlider
from pygame_gui.elements import UILabel, UIButton


from ui.screens.base import Screen

class SettingsScreen(Screen):
    def enter(self) -> None:
        super().enter()
        w, h = self.app.size
        UILabel(pygame.Rect(w//2-220, 60, 440, 60), "Réglage", manager=self.ui)
        for i, txt in enumerate(["Son", "Langues", "Retour"]):
            if i==0:
                UIHorizontalSlider(pygame.Rect(240, (i+1)*108, 480, 80), start_value=0.6, value_range=(0.0, 1.0), manager=self.ui)
            else:
                UIButton(pygame.Rect(240, (i+1)*108, 480, 80), txt, manager=self.ui)

    def process_event(self, event: pygame.event.Event) -> None:
        super().process_event(event)
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            t = event.ui_element.text
            if t == "Langues":
                i = randint(9, 12)
                self.app.audio.play_sfx(f"Minimalist{i}.ogg")
                print("On parle francais ici!")
                pass
            elif t == "Retour":
                self.app.audio.play_sfx("Minimalist13.ogg")
                self.app.screens.set("main_menu")
        elif event.type == pygame_gui.UI_BUTTON_ON_HOVERED:
            i = randint(2, 4)
            self.app.audio.play_sfx(f"Modern{i}.ogg")
        elif event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            self.app.audio.set_master(event.value)
            print("Son : ", int(event.value * 100))
