"""
Profile screen — shown after picking a room, before joining.
Player sets their avatar and username then hits JOIN.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor

from app.components.avatar import AvatarPicker
from app.paths import asset

BG       = "#0EA5E9"
BORDER   = "rgba(255,255,255,0.35)"
BORDER_H = "rgba(255,255,255,0.85)"
TEXT     = "#FFFFFF"
DIM      = "#E0F2FE"
ORANGE   = "#F97316"
ORANGE_H = "#FB923C"
RED      = "rgba(239,68,68,0.80)"

_ADJECTIVES = [
    "splendid","fat","disgusting","fluffy","ancient","tiny","sneaky","mighty",
    "electric","frozen","golden","grumpy","spicy","melted","wobbly","crispy",
    "invisible","soggy","purple","flying","clumsy","savage","lazy","hungry",
    "radioactive","smelly","bouncy","rusty","haunted","shiny",
]
_NOUNS = [
    "banana","fork","bagel","potato","cactus","penguin","meatball","sandwich",
    "pickle","waffle","noodle","baguette","tomato","pretzel","mushroom","mango",
    "donut","porcupine","spatula","walrus","cabbage","anvil","hamster",
    "biscuit","dinosaur","teapot","narwhal","jellybean","avocado",
]


class ProfileScreen(QWidget):
    confirmed  = pyqtSignal(str, str)   # username, avatar_b64
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._avatar_b64 = ""
        self.setStyleSheet("background:transparent;")
        self._build()

    def _build(self):
        try:
            from app import scale as ui_scale; S = ui_scale.get()
        except ImportError: S = 1.0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Centre card ───────────────────────────────────────────────────
        pad = QWidget(); pad.setStyleSheet("background:transparent;")
        pad_l = QVBoxLayout(pad)
        pad_l.setContentsMargins(int(80*S), int(24*S), int(80*S), int(24*S))
        pad_l.setSpacing(0)
        pad_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet("background:transparent;")
        logo_px = QPixmap(asset("icons", "thumbnail.png"))
        if not logo_px.isNull():
            logo_px = logo_px.scaledToHeight(int(90*S), Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(logo_px)
        pad_l.addWidget(logo_lbl)
        pad_l.addSpacing(int(28*S))

        # Avatar picker
        self._avatar = AvatarPicker(size=int(160*S))
        self._avatar.randomize()
        self._avatar.avatar_changed.connect(self._on_avatar_changed)
        self._avatar_b64 = self._avatar.b64()
        pad_l.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignHCenter)

        hint = QLabel("tap to switch avatar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color:{DIM};font-size:{int(14*S)}px;font-weight:600;background:transparent;")
        pad_l.addWidget(hint)
        pad_l.addSpacing(int(24*S))

        # Username row: input + shuffle
        uname_row = QHBoxLayout(); uname_row.setSpacing(int(8*S))

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Enter your name...")
        self._name_input.setMaxLength(20)
        self._name_input.setFixedHeight(int(56*S))
        self._name_input.setStyleSheet(f"""
            QLineEdit{{
                background:rgba(0,0,0,0.18);
                border:2px solid {BORDER};
                border-radius:{int(16*S)}px;
                color:#FFFFFF;
                font-size:{int(22*S)}px;
                font-weight:700;
                letter-spacing:2px;
                padding:0 {int(18*S)}px;
            }}
            QLineEdit:focus{{border:2px solid {BORDER_H};}}
        """)

        shuffle_btn = QPushButton("🔀")
        shuffle_btn.setFixedSize(int(56*S), int(56*S))
        shuffle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        shuffle_btn.setToolTip("Random name")
        shuffle_btn.setStyleSheet(f"""
            QPushButton{{
                background:rgba(255,255,255,0.12);
                border:2px solid {BORDER};
                border-radius:{int(16*S)}px;
                color:#FFFFFF;
                font-size:{int(22*S)}px;
            }}
            QPushButton:hover{{background:rgba(255,255,255,0.22);border:2px solid {BORDER_H};}}
        """)
        shuffle_btn.clicked.connect(self._shuffle_name)
        uname_row.addWidget(self._name_input, stretch=1)
        uname_row.addWidget(shuffle_btn)
        pad_l.addLayout(uname_row)
        pad_l.addSpacing(int(28*S))

        # Buttons row
        btn_row = QHBoxLayout(); btn_row.setSpacing(int(12*S))

        back_btn = QPushButton("← BACK")
        back_btn.setFixedHeight(int(60*S))
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.clicked.connect(self.back_requested)
        back_btn.setStyleSheet(f"""
            QPushButton{{background:{RED};border:none;border-radius:{int(18*S)}px;
            color:#FFF;font-size:{int(16*S)}px;font-weight:800;padding:0 {int(28*S)}px;}}
            QPushButton:hover{{background:rgba(239,68,68,0.95);}}
        """)

        join_btn = QPushButton("JOIN  ▶")
        join_btn.setFixedHeight(int(60*S))
        join_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        join_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        join_btn.clicked.connect(self._on_join)
        join_btn.setStyleSheet(f"""
            QPushButton{{background:{ORANGE};border:none;border-radius:{int(18*S)}px;
            color:#FFF;font-size:{int(18*S)}px;font-weight:800;letter-spacing:2px;}}
            QPushButton:hover{{background:{ORANGE_H};}}
        """)

        btn_row.addWidget(back_btn)
        btn_row.addWidget(join_btn, stretch=1)
        pad_l.addLayout(btn_row)

        root.addWidget(pad)
        self._shuffle_name()   # start with a random name

    def _on_avatar_changed(self, pixmap, b64):
        self._avatar_b64 = b64

    def _shuffle_name(self):
        import random
        adj  = random.choice(_ADJECTIVES)
        noun = random.choice(_NOUNS)
        self._name_input.setText(f"{adj} {noun}")

    def _on_join(self):
        name = self._name_input.text().strip()
        if not name:
            self._name_input.setFocus()
            return
        self.confirmed.emit(name, self._avatar_b64)