from __future__ import annotations
from pathlib import Path
import os

APP_NAME = "ruines_ascendantes"

def default_data_dirs() -> list[Path]:
    paths: list[Path] = []
    # 1) dossier utilisateur (mods)
    home = Path.home()
    paths.append(home / f".{APP_NAME}" / "data")
    # 2) variable d’environnement
    env = os.environ.get("GAME_DATA_DIR")
    if env:
        paths.append(Path(env))
    # 3) fallback projet: src/data/
    here = Path(__file__).resolve()
    src_root = next(p for p in here.parents if (p / "data").exists())  # remonte jusqu’à src/
    paths.append(src_root / "data")
    return paths

def resolve_data_file(category: str, filename: str) -> Path | None:
    for base in default_data_dirs():
        p = base / category / filename
        if p.exists():
            return p
    return None
