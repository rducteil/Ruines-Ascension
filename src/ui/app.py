import pygame, sys, pygame_gui
from pathlib import Path

from ui.audio import AudioManager
from ui.screens.intro import IntroScreen
from ui.screens.main_menu import MainMenuScreen
from ui.screens.settings import SettingsScreen
from ui.screens.load import LoadScreen
from ui.screens.achievments import AchievementsScreen
from ui.screens.character_creation import CharacterCreationScreen

# =================================
# Screen (en state machine)
# =================================
class Screen:
    """Classe de base pour tout les screens UI

        - enter() pour actuver le screen
        - exit() pour désactiver le screen
        - process_event pour utiliser gygame_ui
        - update(dt) puis darw(surface) a chaque frame
    """

    def __init__(self, app: "PygameApp") -> None:
        self.app = app
        self.ui: pygame_gui.UIManager = app.ui
        self.mx: pygame.mixer = app.mx
        self.widgets = []

    def enter(self) -> None:
        # Reset l'UI pour laisser ce screen s'afficher
        self.ui.clear_and_reset()
        self.widgets.clear()

    def exit(self) -> None:
        pass


    def process_event(self, event: pygame.event.Event) -> None:
        # Renvoie le UIManager par default
        self.ui.process_events(event)

    def update(self, dt: float) -> None:
        self.ui.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 22))
        self.ui.draw_ui(surface)

class ScreenManager:
    """Enregistre et set les screens pour swap avec les noms"""

    def __init__(self, app: "PygameApp"): 
        self.app = app
        self._screens: dict[str, Screen] = {}
        self.current: Screen | None = None

    def register(self, name: str, screen: Screen) -> None:
        self._screens[name] = screen

    def set(self, name: str) -> None:
        if self.current:
            self.current.exit()
        self.current = self._screens[name]
        self.current.enter()


# =======================
# App complete (à lancer)
# =======================

class PygameApp:
    def __init__(self, size: tuple[int, int]=(960, 540), title: str = "Tour de Veltharia", font= None, font_size=20):
        pygame.init()
        pygame.display.set_caption(title)

        self.size = size
        self.window = pygame.display.set_mode(size)
        self.clock = pygame.time.Clock()
        self.ui = pygame_gui.UIManager(size)
        self.mx = pygame.mixer
        self.running = False

        self.screens = ScreenManager(self)
        self.session: dict[str, object] = {}    # met player_name, class, etc... pour sauvegarde

        project_root = Path(__file__).resolve().parents[2]
        self.audio = AudioManager(assets_root=project_root / "assets")

        # Active les screens
        self.screens.register("intro", IntroScreen(self))
        self.screens.register("main_menu", MainMenuScreen(self))
        self.screens.register("settings", SettingsScreen(self))
        self.screens.register("load", LoadScreen(self))
        self.screens.register("achievements", AchievementsScreen(self))
        self.screens.register("character_creation", CharacterCreationScreen(self))

        self.screens.set("main_menu")

    def request_quit(self) -> None:
        self.audio.quit()
        self.running = False

    def run(self) -> None:
        self.running = True
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    # Continue le screen courante
                    if self.screens.current:
                        self.screens.current.process_event(event)
            
            if self.screens.current:
                self.screens.current.update(dt)
                self.screens.current.draw(self.window)
            
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = PygameApp()
    app.run()