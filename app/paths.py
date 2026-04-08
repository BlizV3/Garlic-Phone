"""
Asset path resolution that works both in development and when
bundled as a PyInstaller .exe.

Usage anywhere in the project:
    from app.paths import asset
    path = asset("icons/thumbnail.png")          # → assets/icons/thumbnail.png
    path = asset("music/home1.mp3")              # → assets/music/home1.mp3
"""

import os
import sys


def _base_dir() -> str:
    """
    When frozen by PyInstaller, sys._MEIPASS is the temp folder where
    assets are extracted. In development it's just the project root.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    # Development — go up from app/ to project root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR   = _base_dir()
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


def asset(*parts: str) -> str:
    """Return the absolute path to a file inside assets/."""
    return os.path.join(ASSETS_DIR, *parts)