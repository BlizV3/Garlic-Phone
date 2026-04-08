import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor

from app.components.avatar import AvatarPicker

BG         = "#0EA5E9"
CARD_BG    = "rgba(0,0,0,0.15)"
BORDER     = "rgba(255,255,255,0.45)"
BORDER_HOV = "rgba(255,255,255,0.85)"
TEXT_LIGHT = "#FFFFFF"
TEXT_DIM   = "#E0F2FE"
TEXT_GRAY  = "rgba(255,255,255,0.50)"
ORANGE     = "#F97316"
ORANGE_HOV = "#FB923C"
RED        = "rgba(239,68,68,0.75)"
RED_HOV    = "rgba(239,68,68,0.95)"


def make_divider():
    d = QFrame()
    d.setFrameShape(QFrame.Shape.HLine)
    d.setStyleSheet(f"background: {BORDER}; max-height:1px; border:none;")
    return d

def make_vdivider():
    d = QFrame()
    d.setFrameShape(QFrame.Shape.VLine)
    d.setFixedWidth(2)
    d.setStyleSheet("background: rgba(255,255,255,0.20); border:none;")
    return d

def make_input(placeholder: str, center: bool = False) -> QLineEdit:
    inp = QLineEdit()
    inp.setPlaceholderText(placeholder)
    inp.setMinimumHeight(68)
    align = "AlignCenter" if center else "AlignLeft"
    inp.setStyleSheet(f"""
        QLineEdit {{
            background: rgba(0,0,0,0.15);
            border: 2px solid {BORDER};
            border-radius: 16px;
            color: {TEXT_LIGHT};
            font-size: 22px;
            font-weight: 600;
            letter-spacing: 1px;
            padding: 0 22px;
            qproperty-alignment: {align};
        }}
        QLineEdit:focus {{
            border: 2px solid {BORDER_HOV};
            background: rgba(0,0,0,0.22);
        }}
        QLineEdit:disabled {{
            color: rgba(255,255,255,0.4);
            border: 2px solid rgba(255,255,255,0.2);
        }}
    """)
    return inp

def make_setting_row(title: str, subtitle: str, inp: QLineEdit) -> QHBoxLayout:
    """50% left = title+subtitle, 50% right = input."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 6, 0, 6)
    row.setSpacing(32)

    # Left text block
    left = QVBoxLayout()
    left.setSpacing(4)
    left.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    t = QLabel(title)
    t.setStyleSheet(
        f"color:{TEXT_LIGHT}; font-size:22px; font-weight:700; letter-spacing:1px;")
    s = QLabel(subtitle)
    s.setStyleSheet(
        f"color:{TEXT_GRAY}; font-size:14px; font-weight:500; letter-spacing:1px;")
    s.setWordWrap(True)
    left.addWidget(t)
    left.addWidget(s)
    left_w = QWidget()
    left_w.setLayout(left)
    left_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    inp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    row.addWidget(left_w, stretch=1)
    row.addWidget(inp,    stretch=1)
    return row


class JoinScreen(QWidget):
    join_requested = pyqtSignal(str, str, str, str)
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

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

    def _shuffle_name(self):
        import random
        adj  = random.choice(self._ADJECTIVES)
        noun = random.choice(self._NOUNS)
        self._name_input.setText(f"{adj} {noun}")

    def show_error(self, message: str):
        self._error_lbl.setText(message)
        self._error_lbl.setVisible(True)

    def clear_error(self):
        self._error_lbl.setVisible(False)

    def set_loading(self, loading: bool):
        self._join_btn.setEnabled(not loading)
        self._join_btn.setText("CONNECTING…" if loading else "JOIN  ▶")
        self._host_input.setEnabled(not loading)
        self._code_input.setEnabled(not loading)
        self._name_input.setEnabled(not loading)
        if hasattr(self, "_avatar"):
            self._avatar.setEnabled(not loading)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._pad = QWidget()
        self._pad.setStyleSheet("background: transparent;")
        self._pad_layout = QVBoxLayout(self._pad)
        self._pad_layout.setContentsMargins(60, 40, 60, 40)

        card = QWidget()
        card.setObjectName("joinCard")
        card.setStyleSheet(f"""
            QWidget#joinCard {{
                background: {CARD_BG};
                border: 2px solid {BORDER};
                border-radius: 28px;
            }}
            QWidget#joinCard QLabel {{
                background: transparent;
                border: none;
                border-radius: 0px;
            }}
            QWidget#joinCard QWidget {{
                background: transparent;
                border: none;
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 32, 40, 32)
        card_layout.setSpacing(16)

        # Title
        title = QLabel("JOIN A ROOM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:38px; font-weight:900; letter-spacing:3px;")
        card_layout.addWidget(title)
        card_layout.addWidget(make_divider())

        # ── Profile builder ────────────────────────────────────────────────
        profile_row = QHBoxLayout()
        profile_row.setContentsMargins(0, 8, 0, 8)
        profile_row.setSpacing(0)

        # Avatar
        avatar_col = QVBoxLayout()
        avatar_col.setSpacing(10)
        avatar_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar = AvatarPicker(size=140)
        self._avatar.randomize()
        hint = QLabel("tap to switch avatar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:16px; font-weight:600; letter-spacing:1px;")
        avatar_col.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        avatar_col.addWidget(hint)

        # Username
        name_col = QVBoxLayout()
        name_col.setSpacing(14)
        name_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl = QLabel("USERNAME")
        name_lbl.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:16px; font-weight:700; letter-spacing:2px;")
        self._name_input = make_input("Enter your nickname…")
        uname_row = QHBoxLayout()
        uname_row.setSpacing(8)
        uname_row.addWidget(self._name_input, stretch=1)
        shuffle_btn = QPushButton("🔀")
        shuffle_btn.setFixedSize(64, 64)
        shuffle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        shuffle_btn.setToolTip("Random name")
        shuffle_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.12);
                border: 2px solid {BORDER};
                border-radius: 16px;
                color: #FFFFFF;
                font-size: 24px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.22);
                border: 2px solid {BORDER_HOV};
            }}
        """)
        shuffle_btn.clicked.connect(self._shuffle_name)
        uname_row.addWidget(shuffle_btn)
        name_col.addWidget(name_lbl)
        name_col.addLayout(uname_row)
        self._shuffle_name()

        profile_row.addLayout(avatar_col, stretch=1)
        profile_row.addSpacing(24)
        profile_row.addWidget(make_vdivider())
        profile_row.addSpacing(24)
        profile_row.addLayout(name_col, stretch=2)
        card_layout.addLayout(profile_row)
        card_layout.addWidget(make_divider())

        # ── Host IP ────────────────────────────────────────────────────────
        self._host_input = make_input("e.g.  192.168.1.42")
        card_layout.addLayout(make_setting_row(
            "HOST IP ADDRESS",
            "The local IP of the person hosting the room",
            self._host_input
        ))
        card_layout.addWidget(make_divider())

        # ── Room code ──────────────────────────────────────────────────────
        self._code_input = make_input("e.g.  4821", center=True)
        self._code_input.setMaxLength(6)
        card_layout.addLayout(make_setting_row(
            "ROOM CODE",
            "Leave blank if the host has no room code set",
            self._code_input
        ))
        card_layout.addWidget(make_divider())

        # Error
        self._error_lbl = QLabel("")
        self._error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_lbl.setStyleSheet(
            "color:#FCA5A5; font-size:18px; font-weight:600; letter-spacing:1px;")
        self._error_lbl.setVisible(False)
        card_layout.addWidget(self._error_lbl)

        card_layout.addStretch()

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        back_btn = QPushButton("← BACK")
        back_btn.setFixedHeight(72)
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.clicked.connect(self.back_requested)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {RED};
                border: 2px solid rgba(239,68,68,0.4);
                border-radius: 36px;
                color: {TEXT_LIGHT};
                font-size: 22px;
                font-weight: 700;
                letter-spacing: 2px;
                padding: 0 36px;
            }}
            QPushButton:hover {{ background: {RED_HOV}; }}
        """)

        self._join_btn = QPushButton("JOIN  ▶")
        self._join_btn.setFixedHeight(72)
        self._join_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._join_btn.clicked.connect(self._on_join)
        self._join_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._join_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ORANGE};
                border: 3px solid rgba(249,115,22,0.4);
                border-radius: 36px;
                color: #FFFFFF;
                font-size: 22px;
                font-weight: 800;
                letter-spacing: 3px;
                padding: 0 48px;
            }}
            QPushButton:hover {{ background: {ORANGE_HOV}; }}
            QPushButton:disabled {{
                background: rgba(249,115,22,0.4);
                color: rgba(255,255,255,0.5);
            }}
        """)

        btn_row.addWidget(back_btn)
        btn_row.addWidget(self._join_btn)
        card_layout.addLayout(btn_row)

        self._pad_layout.addWidget(card)
        outer.addWidget(self._pad)

    def _on_join(self):
        self.clear_error()
        host = self._host_input.text().strip()
        code = self._code_input.text().strip()
        name = self._name_input.text().strip()
        if not host:
            self.show_error("Please enter the host's IP address")
            return
        if not name:
            self.show_error("Please enter your name")
            return
        self.set_loading(True)
        self.join_requested.emit(host, code, name, self._avatar.b64())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from app import scale as ui_scale
        S = ui_scale.get()
        pad_h = max(int(60*S), int(self.width()  * 0.07))
        pad_v = max(int(40*S), int(self.height() * 0.05))
        self._pad_layout.setContentsMargins(pad_h, pad_v, pad_h, pad_v)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = QMainWindow()
    w.setMinimumSize(800, 700)
    w.resize(1282, 890)
    w.setStyleSheet(f"background: {BG};")
    screen = JoinScreen()
    w.setCentralWidget(screen)
    screen.join_requested.connect(
        lambda ip, code, name, av: print(f"Join — IP:{ip} code:{code} name:{name}"))
    screen.back_requested.connect(lambda: print("← Back"))
    w.show()
    sys.exit(app.exec())