from __future__ import annotations
"""Résolution des chemins de données (mods → env → src/data)."""

from pathlib import Path
import os

APP_NAME = "ruines_ascendantes"

def default_data_dirs() -> list[Path]:
    dirs: list[Path] = []

    # 1) dossier utilisateur (mods)
    home = Path.home()
    dirs.append(home / f".{APP_NAME}" / "data")

    # 2) variable d’environnement
    env = os.environ.get("GAME_DATA_DIR")
    if env:
        dirs.append(Path(env))

    # 3) fallback projet: src/data/
    here = Path(__file__).resolve()
    # remonte jusqu'à 'src/' puis 'src/data'
    for p in here.parents:
        maybe = p / "data"
        if maybe.is_dir():
            dirs.append(maybe)
            break
    
    return dirs

def iter_category_files(category: str, suffix: str = ".json"):
    """Itère tous les fichiers d'une catégorie ('events', 'items', ...) dans l'ordre de priorité."""
    for base in default_data_dirs():
        folder = base / category
        if folder.is_dir():
            yield from folder.glob(f"*{suffix}")
