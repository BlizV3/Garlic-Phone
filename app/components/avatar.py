import os
import base64
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QPixmap,
    QFont, QCursor, QPainterPath
)

TEXT_LIGHT = "#FFFFFF"

AVATARS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "assets", "avatars"
)

AVATAR_FILES = [
    "default.png",
    "cat.png",
    "dog.png",
    "hamster.png",
    "minion.png",
    "rabbit.png",
]


class AvatarPicker(QWidget):
    """
    Circular avatar widget. Click to cycle through preset avatars.
    Emits `avatar_changed(pixmap, b64_string)` when the avatar changes.
    Left-click  → next avatar
    Right-click → previous avatar
    """
    avatar_changed = pyqtSignal(QPixmap, str)

    BORDER = 3

    def __init__(self, size: int = 110, parent=None):
        super().__init__(parent)
        self._size  = size
        self._index = 0
        self.setFixedSize(size, size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._hovered    = False
        self._pixmap     = None
        self._raw_pixmap = None
        self._b64        = ""
        self._load_avatar(0)

    def randomize(self):
        import random
        self._load_avatar(random.randint(0, len(AVATAR_FILES) - 1))
        self.avatar_changed.emit(self._raw_pixmap or QPixmap(), self._b64)

    def b64(self) -> str:
        return self._b64

    def _load_avatar(self, index: int):
        self._index = index % len(AVATAR_FILES)
        path = os.path.join(AVATARS_DIR, AVATAR_FILES[self._index])
        px = QPixmap(path)
        if px.isNull():
            self._raw_pixmap = None
            self._pixmap     = None
            self._b64        = ""
            self.update()
            return
        self._raw_pixmap = px
        self._rescale()
        try:
            with open(path, "rb") as f:
                self._b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            self._b64 = ""
        self.update()
        self.avatar_changed.emit(px, self._b64)

    def _radius(self) -> int:
        return self._size // 2 - 4

    def _rescale(self):
        if self._raw_pixmap is None:
            return
        r = self._radius()
        self._pixmap = self._raw_pixmap.scaled(
            r * 2, r * 2,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._load_avatar(self._index + 1)
        elif event.button() == Qt.MouseButton.RightButton:
            self._load_avatar(self._index - 1)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = cy = self._size // 2
        r  = self._radius()
        b  = self.BORDER

        border_color = QColor(255,255,255,200) if self._hovered else QColor(255,255,255,115)
        p.setPen(QPen(border_color, b))
        p.setBrush(QBrush(QColor("#0369A1")))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        clip = QPainterPath()
        clip.addEllipse(cx - r + b, cy - r + b, (r - b) * 2, (r - b) * 2)
        p.setClipPath(clip)

        if self._pixmap:
            px = cx - self._pixmap.width()  // 2
            py = cy - self._pixmap.height() // 2
            p.drawPixmap(px, py, self._pixmap)
        else:
            font = QFont()
            font.setPointSize(max(10, r // 2))
            p.setFont(font)
            p.setPen(QColor(TEXT_LIGHT))
            p.drawText(QRect(cx - r, cy - r, r * 2, r * 2),
                       Qt.AlignmentFlag.AlignCenter, "🐦")

        p.setClipping(False)

        if self._hovered:
            p.setBrush(QBrush(QColor(255, 255, 255, 20)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - r + b, cy - r + b, (r - b) * 2, (r - b) * 2)