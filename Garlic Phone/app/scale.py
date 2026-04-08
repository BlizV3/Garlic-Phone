"""
Global UI scale factor — set once at startup based on monitor resolution.
All screens read this to scale fonts, padding and fixed sizes.
"""

_scale: float = 1.0

def set_scale(s: float):
    global _scale
    _scale = max(0.5, s)

def get() -> float:
    return _scale

def px(base: int) -> int:
    """Scale a pixel value."""
    return max(1, int(base * _scale))

def pt(base: int) -> int:
    """Scale a font point size."""
    return max(6, int(base * _scale))