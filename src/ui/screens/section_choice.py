from __future__ import annotations
import pygame, pygame_gui
from ui.screens.base import GameScreen

# Exemples a changer
class SectionChoiceScreen(GameScreen):
    def enter(self) -> None:
        super().enter()
        self.scene.set_caption("Choix de section")
        self.dialog.show_text("Où allez-vous ?")
        self.dialog.show_choices(["Combat", "Événement", "Ravitaillement"])

    def process_event(self, event: pygame.event.Event) -> None:
        super().process_event(event)
        choice = self.dialog.handle_event(event)
        if choice is not None:
            if choice == 0: self.app.screens.set("combat")
            elif choice == 1: self.app.screens.set("event")
            else: self.app.screens.set("supply")
