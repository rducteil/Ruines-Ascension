import pygame, sys

from game.game_loop import GameLoop
from src.ui.app import PygameApp

def main():
    io = PygameApp()
    loop = GameLoop(io=io)
    loop.run()

if __name__ == "__main__":
    main()