import sys
import random
import string

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QCursor, QPainterPath

from app.components.avatar import AvatarPicker

BG         = "#0EA5E9"
CARD_BG    = "rgba(0,0,0,0.15)"
BORDER     = "rgba(255,255,255,0.45)"
BORDER_HOV = "rgba(255,255,255,0.85)"
TEXT_LIGHT = "#FFFFFF"
TEXT_DIM   = "#E0F2FE"
ORANGE     = "#F97316"
ORANGE_HOV = "#FB923C"
TOGGLE_ON  = "#F97316"


# ── Toggle switch ──────────────────────────────────────────────────────────────
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on     = True
        self.setFixedSize(96, 52)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._start_x = 6
        self._end_x   = 46
        self._anim_x  = float(self._end_x)

    def is_on(self): return self._on

    def set_on(self, value: bool):
        self._on    = value
        self._anim_x = float(self._end_x if value else self._start_x)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on = not self._on
            self._anim_x = float(self._end_x if self._on else self._start_x)
            self.update()
            self.toggled.emit(self._on)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r    = h // 2
        track_color = QColor(TOGGLE_ON) if self._on else QColor(0, 0, 0, 64)
        p.setBrush(QBrush(track_color))
        p.setPen(QPen(QColor(255, 255, 255, 80), 2))
        p.drawRoundedRect(0, 0, w, h, r, r)
        knob_r = h - 14
        knob_x = int(self._anim_x)
        p.setBrush(QBrush(QColor(TEXT_LIGHT)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(knob_x, 7, knob_r, knob_r)


# ── Spinner ────────────────────────────────────────────────────────────────────
class SpinnerWidget(QWidget):
    value_changed = pyqtSignal(int)
    MIN, MAX = 2, 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 4
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        self._down = self._make_btn("−")
        self._down.clicked.connect(self._decrement)

        self._display = QLabel(str(self._value))
        self._display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._display.setMinimumWidth(72)
        self._display.setStyleSheet(f"color:{TEXT_LIGHT}; font-size:42px; font-weight:800;")

        self._up = self._make_btn("+")
        self._up.clicked.connect(self._increment)

        layout.addWidget(self._down)
        layout.addWidget(self._display)
        layout.addWidget(self._up)
        self._update_buttons()

    def _make_btn(self, symbol):
        btn = QPushButton(symbol)
        btn.setFixedSize(64, 64)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.15);
                border: 2px solid {BORDER};
                border-radius: 32px;
                color: {TEXT_LIGHT};
                font-size: 32px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.28);
                border: 2px solid {BORDER_HOV};
            }}
            QPushButton:disabled {{
                background: rgba(255,255,255,0.05);
                border: 2px solid rgba(255,255,255,0.15);
                color: rgba(255,255,255,0.3);
            }}
        """)
        return btn

    def _increment(self):
        if self._value < self.MAX:
            self._value += 1; self._refresh()

    def _decrement(self):
        if self._value > self.MIN:
            self._value -= 1; self._refresh()

    def _refresh(self):
        self._display.setText(str(self._value))
        self._update_buttons()
        self.value_changed.emit(self._value)

    def _update_buttons(self):
        self._down.setEnabled(self._value > self.MIN)
        self._up.setEnabled(self._value < self.MAX)

    def value(self): return self._value


# ── Helpers ────────────────────────────────────────────────────────────────────
def make_row(label_text, control):
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 8, 0, 8)
    layout.setSpacing(16)
    lbl = QLabel(label_text)
    lbl.setStyleSheet(f"color:{TEXT_LIGHT}; font-size:26px; font-weight:700; letter-spacing:1px;")
    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout.addWidget(lbl)
    layout.addWidget(control, alignment=Qt.AlignmentFlag.AlignRight)
    return row

def make_divider():
    d = QFrame()
    d.setFrameShape(QFrame.Shape.HLine)
    d.setStyleSheet("background: rgba(255,255,255,0.15); max-height:1px;")
    return d


# ── Create screen ──────────────────────────────────────────────────────────────
class CreateScreen(QWidget):
    create_requested = pyqtSignal(int, bool, str, str)
    back_requested   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    def _build_ui(self):
        from app import scale as ui_scale
        S = ui_scale.get()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QWidget()
        self._card.setObjectName("settingsCard")
        self._card.setStyleSheet(f"""
            QWidget#settingsCard {{
                background: {CARD_BG};
                border: 2px solid {BORDER};
                border-radius: {int(28*S)}px;
            }}
        """)
        self._card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        card_layout = QVBoxLayout(self._card)
        card_layout.setSpacing(int(24*S))
        card_layout.setContentsMargins(int(40*S), int(32*S), int(40*S), int(32*S))

        # Title
        title = QLabel("CREATE ROOM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT_LIGHT}; font-size:{int(38*S)}px; font-weight:900; letter-spacing:4px;")
        card_layout.addWidget(title)
        card_layout.addWidget(make_divider())

        # ── Profile builder: avatar left | divider | username right ──────────
        profile_row = QHBoxLayout()
        profile_row.setContentsMargins(0, 8, 0, 8)
        profile_row.setSpacing(0)

        # Left — avatar
        avatar_col = QVBoxLayout()
        avatar_col.setSpacing(10)
        avatar_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar = AvatarPicker(size=140)
        self._avatar.randomize()
        hint = QLabel("tap to switch avatar")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color:{TEXT_DIM}; font-size:16px; font-weight:600; letter-spacing:1px;")
        avatar_col.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        avatar_col.addWidget(hint)

        # Vertical divider
        v_div = QFrame()
        v_div.setFrameShape(QFrame.Shape.VLine)
        v_div.setFixedWidth(2)
        v_div.setStyleSheet("background: rgba(255,255,255,0.20); border: none;")

        # Right — username
        name_col = QVBoxLayout()
        name_col.setSpacing(14)
        name_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl = QLabel("USERNAME")
        name_lbl.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:16px; font-weight:700; letter-spacing:2px;")
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Enter name...")
        self._username_input.setMaxLength(20)
        self._username_input.setFixedHeight(64)
        self._username_input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(0,0,0,0.18);
                border: 2px solid {BORDER};
                border-radius: 16px;
                color: {TEXT_LIGHT};
                font-size: 26px;
                font-weight: 700;
                letter-spacing: 2px;
                padding: 0 20px;
            }}
            QLineEdit:focus {{ border: 2px solid {BORDER_HOV}; }}
        """)
        # Username row: input + shuffle button
        uname_row = QHBoxLayout()
        uname_row.setSpacing(8)
        uname_row.addWidget(self._username_input, stretch=1)
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
        self._shuffle_name()   # start with a random name

        profile_row.addLayout(avatar_col, stretch=1)
        profile_row.addSpacing(24)
        profile_row.addWidget(v_div)
        profile_row.addSpacing(24)
        profile_row.addLayout(name_col, stretch=2)

        card_layout.addLayout(profile_row)
        card_layout.addWidget(make_divider())

        # Player size
        self._spinner = SpinnerWidget()
        card_layout.addWidget(make_row("Player Size", self._spinner))
        card_layout.addWidget(make_divider())

        # Toggle
        self._toggle = ToggleSwitch()
        self._toggle.toggled.connect(self._on_toggle)
        card_layout.addWidget(make_row("Require Room Code", self._toggle))
        card_layout.addWidget(make_divider())

        # Code row
        self._code_row = QWidget()
        self._code_row.setStyleSheet("background: transparent;")
        code_layout = QHBoxLayout(self._code_row)
        code_layout.setContentsMargins(0, 8, 0, 8)
        code_layout.setSpacing(14)

        code_lbl = QLabel("Room Code")
        code_lbl.setStyleSheet(f"color:{TEXT_LIGHT}; font-size:26px; font-weight:700; letter-spacing:1px;")
        code_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._code_input = QLineEdit()
        self._code_input.setMaxLength(6)
        self._code_input.setFixedWidth(160)
        self._code_input.setFixedHeight(64)
        self._code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._code_input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(0,0,0,0.18);
                border: 2px solid {BORDER};
                border-radius: 16px;
                color: {TEXT_LIGHT};
                font-size: 28px;
                font-weight: 800;
                letter-spacing: 4px;
                qproperty-alignment: AlignCenter;
            }}
            QLineEdit:focus {{ border: 2px solid {BORDER_HOV}; }}
        """)
        self._code_input.setText(self._random_code())

        self._rand_btn = QPushButton("↺")
        self._rand_btn.setFixedSize(64, 64)
        self._rand_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._rand_btn.setToolTip("Randomise code")
        self._rand_btn.clicked.connect(self._randomise_code)
        self._rand_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.15);
                border: 2px solid {BORDER};
                border-radius: 16px;
                color: {TEXT_LIGHT};
                font-size: 30px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.28);
                border: 2px solid {BORDER_HOV};
            }}
        """)

        code_layout.addWidget(code_lbl)
        code_layout.addWidget(self._code_input)
        code_layout.addWidget(self._rand_btn)
        card_layout.addWidget(self._code_row)
        card_layout.addWidget(make_divider())
        card_layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self._back_btn = QPushButton("← BACK")
        self._back_btn.setFixedHeight(72)
        self._back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._back_btn.clicked.connect(self.back_requested)
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,68,68,0.75);
                border: 2px solid rgba(239,68,68,0.4);
                border-radius: 36px;
                color: {TEXT_LIGHT};
                font-size: 22px;
                font-weight: 700;
                letter-spacing: 2px;
                padding: 0 36px;
            }}
            QPushButton:hover {{
                background: rgba(239,68,68,0.95);
                border: 2px solid rgba(239,68,68,0.7);
            }}
        """)

        self._create_btn = QPushButton("CREATE  ▶")
        self._create_btn.setFixedHeight(72)
        self._create_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._create_btn.clicked.connect(self._on_create)
        self._create_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_create_style(False)
        self._create_btn.enterEvent = lambda e: self._apply_create_style(True)
        self._create_btn.leaveEvent = lambda e: self._apply_create_style(False)

        btn_row.addWidget(self._back_btn)
        btn_row.addWidget(self._create_btn)
        card_layout.addLayout(btn_row)

        # Pad
        self._pad = QWidget()
        self._pad.setStyleSheet("background: transparent;")
        self._pad_layout = QVBoxLayout(self._pad)
        self._pad_layout.setContentsMargins(60, 40, 60, 40)
        self._pad_layout.addWidget(self._card)
        outer.addWidget(self._pad)

    def _apply_create_style(self, hovered):
        bg = ORANGE_HOV if hovered else ORANGE
        self._create_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: 3px solid rgba(249,115,22,0.4);
                border-radius: 36px;
                color: #FFFFFF;
                font-size: 22px;
                font-weight: 800;
                letter-spacing: 3px;
                padding: 0 48px;
            }}
        """)

    def _random_code(self):
        return ''.join(random.choices(string.digits, k=4))

    def _randomise_code(self):
        self._code_input.setText(self._random_code())

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
        self._username_input.setText(f"{adj} {noun}")

    def _on_toggle(self, on):
        self._code_row.setVisible(on)

    def _on_create(self):
        max_players  = self._spinner.value()
        require_code = self._toggle.is_on()
        code         = self._code_input.text().strip() if require_code else ""
        username     = self._username_input.text().strip() or "Host"
        self.create_requested.emit(max_players, require_code, code, self._avatar.b64())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from app import scale as ui_scale
        S = ui_scale.get()
        pad_h = max(int(40*S), int(self.width()  * 0.07))
        pad_v = max(int(30*S), int(self.height() * 0.05))
        self._pad_layout.setContentsMargins(pad_h, pad_v, pad_h, pad_v)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = QMainWindow()
    w.setMinimumSize(800, 700)
    w.resize(1282, 890)
    w.setStyleSheet("background: #0EA5E9;")
    screen = CreateScreen()
    w.setCentralWidget(screen)
    screen.create_requested.connect(lambda p, r, c, a: print(f"Create: {p} players, code={c}"))
    screen.back_requested.connect(lambda: print("← Back"))
    w.show()
    sys.exit(app.exec())