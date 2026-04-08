import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPixmap

BG             = "#0EA5E9"
BTN_BG         = "rgba(0,0,0,0.15)"
BTN_HOVER      = "rgba(0,0,0,0.28)"
BTN_BORDER     = "rgba(255,255,255,0.45)"
BTN_BORDER_HOV = "rgba(255,255,255,0.9)"
TEXT_LIGHT     = "#FFFFFF"
TEXT_DIM       = "#E0F2FE"

from app.paths import asset as _asset

def load_icon(name: str, size: int = 80) -> QPixmap:
    path = _asset("icons", name)
    px   = QPixmap(path)
    if px.isNull():
        return QPixmap()
    return px.scaled(size, size,
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)


# ── Big choice button ─────────────────────────────────────────────────────────
class ChoiceButton(QWidget):
    clicked = pyqtSignal()

    ICON_MAP = {"join": "enter.png", "create": "build.png"}

    def __init__(self, kind: str, label: str, parent=None):
        super().__init__(parent)
        self.kind     = kind
        self._hovered = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumSize(120, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._card = QWidget()
        self._card.setObjectName("card")
        self._apply_card_style(False)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(16, 20, 16, 18)
        card_layout.setSpacing(10)

        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._base_px = load_icon(self.ICON_MAP.get(kind, "enter.png"))
        self._icon_lbl.setPixmap(self._base_px)
        card_layout.addWidget(self._icon_lbl, stretch=3)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_label_style(False)
        card_layout.addWidget(self._label, stretch=1)

        layout.addWidget(self._card)

    def _apply_card_style(self, hovered: bool):
        bg     = BTN_HOVER      if hovered else BTN_BG
        border = BTN_BORDER_HOV if hovered else BTN_BORDER
        self._card.setStyleSheet(f"""
            QWidget#card {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 20px;
            }}
        """)

    def _apply_label_style(self, hovered: bool):
        self._label.setStyleSheet(f"""
            color: {TEXT_LIGHT};
            font-size: 36px;
            font-weight: 900;
            letter-spacing: 4px;
            background: transparent;
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Scale icon to 70% of available space so it fits with breathing room
        available = int(min(self._icon_lbl.width(), self._icon_lbl.height()) * 0.70)
        if available > 10:
            px = load_icon(self.ICON_MAP.get(self.kind, "enter.png"), size=available)
            self._icon_lbl.setPixmap(px)
        # Label always matches FREE DRAW style
        self._label.setStyleSheet(f"""
            color: {TEXT_LIGHT};
            font-size: 36px;
            font-weight: 900;
            letter-spacing: 4px;
            background: transparent;
        """)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_card_style(True)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_card_style(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ── Home screen ───────────────────────────────────────────────────────────────
class HomeScreen(QWidget):
    join_clicked      = pyqtSignal()
    create_clicked    = pyqtSignal()
    free_draw_clicked = pyqtSignal()
    photos_clicked    = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    def _build_ui(self):
        from app import scale as ui_scale
        S = ui_scale.get()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 0)
        root.setSpacing(0)

        # Thumbnail image replacing text title
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("background: transparent;")
        thumb_px = load_icon("thumbnail.png", int(280 * S))
        if not thumb_px.isNull():
            self.title.setPixmap(thumb_px)
        else:
            self.title.setText("🧄 GARLIC PHONE")
            self.title.setStyleSheet(f"""
                color: {TEXT_LIGHT};
                font-size: {int(48*S)}px;
                font-weight: 900;
                letter-spacing: 4px;
                background: transparent;
            """)
        root.addWidget(self.title)

        # Outer container — cards + free draw button share margins
        outer_container = QWidget()
        outer_container.setStyleSheet("background: transparent;")
        outer_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._outer_layout = QVBoxLayout(outer_container)
        self._outer_layout.setContentsMargins(int(160*S), int(20*S), int(160*S), int(40*S))
        self._outer_layout.setSpacing(int(16*S))

        # JOIN / CREATE card row
        btn_container = QWidget()
        btn_container.setStyleSheet("background: transparent;")
        self._btn_layout = QHBoxLayout(btn_container)
        self._btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_layout.setSpacing(16)

        self.join_btn   = ChoiceButton("join",   "JOIN")
        self.create_btn = ChoiceButton("create", "CREATE")
        self.join_btn.clicked.connect(self.join_clicked)
        self.create_btn.clicked.connect(self.create_clicked)

        self._btn_layout.addWidget(self.join_btn)
        self._btn_layout.addWidget(self.create_btn)
        self._outer_layout.addWidget(btn_container, stretch=1)

        # ── Free Draw button — icon pinned left-middle, text right ──────
        icon_sz = int(56 * S)
        btn_h   = int(100 * S)
        fs_btn  = int(31 * S)

        free_draw_widget = QWidget()
        free_draw_widget.setFixedHeight(btn_h)
        free_draw_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        free_draw_widget.setStyleSheet(f"""
            QWidget {{
                background: rgba(0,0,0,0.20);
                border: 2px solid rgba(255,255,255,0.45);
                border-radius: 20px;
            }}
            QWidget:hover {{
                background: rgba(0,0,0,0.35);
                border: 2px solid rgba(255,255,255,0.85);
            }}
        """)

        fd_layout = QHBoxLayout(free_draw_widget)
        fd_layout.setContentsMargins(int(20*S), 0, int(20*S), 0)
        fd_layout.setSpacing(0)

        # Pencil icon — left side
        pencil_lbl = QLabel()
        pencil_lbl.setStyleSheet("background: transparent; border: none;")
        pencil_px = load_icon("pencil.png", icon_sz)
        if not pencil_px.isNull():
            pencil_lbl.setPixmap(pencil_px)
        pencil_lbl.setFixedSize(icon_sz, icon_sz)
        pencil_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fd_text = QLabel("FREE DRAW")
        fd_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        fd_text.setStyleSheet(f"""
            color: {TEXT_LIGHT};
            font-size: {fs_btn}px;
            font-weight: 900;
            letter-spacing: 4px;
            background: transparent;
            border: none;
        """)

        fd_layout.addWidget(pencil_lbl)
        fd_layout.addWidget(fd_text, stretch=1)

        # Make the whole widget clickable
        free_draw_widget.mousePressEvent = lambda e: self.free_draw_clicked.emit()
        self._free_draw_btn = free_draw_widget

        # Bottom row — FREE DRAW (left) | MY PHOTOS (right), equal width
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(int(16*S))
        bottom_row.addWidget(free_draw_widget, stretch=1)

        # MY PHOTOS button — same style and height as FREE DRAW
        photos_widget = QWidget()
        photos_widget.setFixedHeight(btn_h)
        photos_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        photos_widget.setStyleSheet(f"""
            QWidget {{
                background: rgba(0,0,0,0.20);
                border: 2px solid rgba(255,255,255,0.45);
                border-radius: 20px;
            }}
            QWidget:hover {{
                background: rgba(0,0,0,0.35);
                border: 2px solid rgba(255,255,255,0.85);
            }}
        """)
        ph_layout = QHBoxLayout(photos_widget)
        ph_layout.setContentsMargins(int(20*S), 0, int(20*S), 0)
        ph_layout.setSpacing(0)

        photos_icon_lbl = QLabel("🖼")
        photos_icon_lbl.setFixedSize(icon_sz, icon_sz)
        photos_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        photos_icon_lbl.setStyleSheet(f"background: transparent; border: none; font-size: {int(32*S)}px;")

        photos_text = QLabel("MY PHOTOS")
        photos_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        photos_text.setStyleSheet(f"""
            color: {TEXT_LIGHT};
            font-size: {fs_btn}px;
            font-weight: 900;
            letter-spacing: 4px;
            background: transparent;
            border: none;
        """)

        ph_layout.addWidget(photos_icon_lbl)
        ph_layout.addWidget(photos_text, stretch=1)

        photos_widget.mousePressEvent = lambda e: self.photos_clicked.emit()

        bottom_row.addWidget(photos_widget, stretch=1)
        self._outer_layout.addLayout(bottom_row, stretch=0)

        root.addWidget(outer_container, stretch=4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        from app import scale as ui_scale
        S        = ui_scale.get()
        scale    = min(self.width(), self.height()) / 500.0
        pad_h    = max(int(80*S), int(self.width()  * 0.18))
        pad_v    = max(int(20*S), int(self.height() * 0.04))
        gap      = int(16 * S)

        # Rescale thumbnail to fit available width
        avail_w = max(150, int(self.width() * 0.28))
        thumb_px = load_icon("thumbnail.png", avail_w)
        if not thumb_px.isNull():
            self.title.setPixmap(thumb_px)

        self._outer_layout.setContentsMargins(pad_h, pad_v, pad_h, int(pad_v * 1.5))
        self._btn_layout.setSpacing(gap)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = QMainWindow()
    w.setMinimumSize(480, 360)
    w.resize(700, 500)
    w.setStyleSheet(f"background: {BG};")
    screen = HomeScreen()
    w.setCentralWidget(screen)
    screen.join_clicked.connect(lambda: print("→ Join"))
    screen.create_clicked.connect(lambda: print("→ Create"))
    w.show()
    sys.exit(app.exec())