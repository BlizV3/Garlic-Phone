import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QFrame,
    QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QPixmap,
    QFont, QCursor, QPainterPath
)

BG           = "#0EA5E9"
PANEL_BG     = "rgba(0,0,0,0.18)"
BORDER       = "rgba(255,255,255,0.35)"
BORDER_HOV   = "rgba(255,255,255,0.85)"
TEXT_LIGHT   = "#FFFFFF"
TEXT_DIM     = "#E0F2FE"
TEXT_GHOST   = "rgba(255,255,255,0.30)"
ORANGE       = "#F97316"
ORANGE_HOV   = "#FB923C"
SLOT_FILLED  = "rgba(255,255,255,0.12)"
SLOT_EMPTY   = "rgba(255,255,255,0.05)"


# ── Circular mini-avatar ──────────────────────────────────────────────────────
class MiniAvatar(QWidget):
    SIZE = 88   # doubled from 44

    def __init__(self, pixmap: QPixmap = None, ghost: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._pixmap = pixmap
        self._ghost  = ghost

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        sz = self.width()          # use actual widget size, not hardcoded
        cx = cy = sz // 2
        r  = cx - 2

        if self._ghost:
            p.setBrush(QBrush(QColor(255, 255, 255, 25)))
            p.setPen(QPen(QColor(255, 255, 255, 50), 1.5))
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            # ghost silhouette
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 255, 255, 40)))
            head_r = int(r * 0.38)
            p.drawEllipse(cx - head_r, cy - r + 6, head_r * 2, head_r * 2)
            body_w = int(r * 1.1)
            body_h = int(r * 0.7)
            p.drawRoundedRect(cx - body_w // 2, cy + 2, body_w, body_h, 8, 8)
        else:
            p.setBrush(QBrush(QColor("#0369A1")))
            p.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            if self._pixmap:
                clip = QPainterPath()
                clip.addEllipse(cx - r + 2, cy - r + 2, (r - 2) * 2, (r - 2) * 2)
                p.setClipPath(clip)
                scaled = self._pixmap.scaled(
                    sz, sz,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                p.drawPixmap(cx - scaled.width() // 2, cy - scaled.height() // 2, scaled)
                p.setClipping(False)
            else:
                # default emoji-style face
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(255, 255, 255, 200)))
                eye_r = int(r * 0.18)
                p.drawEllipse(cx - int(r * 0.32) - eye_r, cy - eye_r - 2, eye_r * 2, eye_r * 2)
                p.drawEllipse(cx + int(r * 0.32) - eye_r, cy - eye_r - 2, eye_r * 2, eye_r * 2)
                # smile arc workaround — small ellipse clipped
                p.drawRoundedRect(cx - int(r * 0.3), cy + int(r * 0.1),
                                  int(r * 0.6), int(r * 0.22), 4, 4)


# ── Single player slot ────────────────────────────────────────────────────────
class PlayerSlot(QWidget):
    def __init__(self, username: str = "", is_host: bool = False,
                 pixmap: QPixmap = None, empty: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(105)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        bg = SLOT_EMPTY if empty else SLOT_FILLED
        self.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 20, 0)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        avatar = MiniAvatar(pixmap=pixmap, ghost=empty)
        layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignVCenter)

        if not empty:
            name_row = QHBoxLayout()
            name_row.setSpacing(8)
            name_row.setContentsMargins(0, 0, 0, 0)

            if is_host:
                crown = QLabel("👑")
                crown.setStyleSheet("font-size: 22px;")
                name_row.addWidget(crown)

            name = QLabel(username)
            name.setStyleSheet(f"""
                color: {TEXT_LIGHT};
                font-size: 28px;
                font-weight: 700;
                letter-spacing: 1px;
            """)
            name_row.addWidget(name)
            name_row.addStretch()

            name_widget = QWidget()
            name_widget.setStyleSheet("background: transparent; border: none;")
            name_widget.setLayout(name_row)
            layout.addWidget(name_widget, stretch=1)
        else:
            ghost_lbl = QLabel("EMPTY")
            ghost_lbl.setStyleSheet(f"""
                color: {TEXT_GHOST};
                font-size: 20px;
                font-weight: 600;
                letter-spacing: 2px;
            """)
            layout.addWidget(ghost_lbl, stretch=1)


# ── Divider ───────────────────────────────────────────────────────────────────
def make_divider():
    d = QFrame()
    d.setFrameShape(QFrame.Shape.HLine)
    d.setStyleSheet(f"background: {BORDER}; max-height: 1px; border: none;")
    return d


# ── Setting row (label + value, read-only display) ────────────────────────────
def make_setting_row(label: str, value: str) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent; border: none;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 6, 0, 6)
    layout.setSpacing(12)

    lbl = QLabel(label)
    lbl.setStyleSheet(f"""
        color: {TEXT_DIM};
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 1px;
    """)

    val = QLabel(value)
    val.setAlignment(Qt.AlignmentFlag.AlignRight)
    val.setStyleSheet(f"""
        color: {TEXT_LIGHT};
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 1px;
    """)

    layout.addWidget(lbl, stretch=1)
    layout.addWidget(val)
    return row


# ── Setting dropdown ──────────────────────────────────────────────────────────
class SettingDropdown(QWidget):
    """
    A labelled setting row with a button that shows the current value.
    Clicking opens a popup list of options. Selecting one closes the popup
    and updates the button label.
    """
    changed = pyqtSignal(int)   # emits selected index

    def __init__(self, label: str, options: list, selected: int = 0, parent=None):
        super().__init__(parent)
        self._options  = options
        self._selected = selected
        self._popup    = None
        self.setStyleSheet("background: transparent;")
        self._build(label)

    def _build(self, label: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # Strip emojis — keep only text after the first two chars if they're emoji
        clean = label
        for emoji in ["⏱  ", "🔄  ", "🔀  "]:
            clean = clean.replace(emoji, "")

        lbl = QLabel(clean)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"""
            color: {TEXT_LIGHT}; font-size: 14px;
            font-weight: 900; letter-spacing: 2px;
            background: transparent;
        """)
        root.addWidget(lbl)

        # Dropdown trigger button — 50% taller
        self._btn = QPushButton()
        self._btn.setFixedHeight(78)
        self._btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn.clicked.connect(self._toggle_popup)
        self._update_btn()
        root.addWidget(self._btn)

    def _update_btn(self):
        text = self._options[self._selected] if self._options else "—"
        self._btn.setText(f"  {text}  ▾")
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.12);
                border: 2px solid {BORDER};
                border-radius: 14px;
                color: {TEXT_LIGHT};
                font-size: 18px;
                font-weight: 700;
                text-align: left;
                padding: 0 16px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.20);
                border: 2px solid {BORDER_HOV};
            }}
        """)

    def _toggle_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.hide()
            return
        self._show_popup()

    def _show_popup(self):
        # Build popup anchored below the button
        self._popup = QWidget(self.window(), Qt.WindowType.Popup)
        self._popup.setStyleSheet(f"""
            QWidget {{
                background: #0C4A6E;
                border: 2px solid {BORDER_HOV};
                border-radius: 14px;
            }}
        """)
        pop_l = QVBoxLayout(self._popup)
        pop_l.setContentsMargins(6, 6, 6, 6)
        pop_l.setSpacing(3)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.08);
                width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.40);
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_l = QVBoxLayout(inner)
        inner_l.setContentsMargins(0, 0, 0, 0)
        inner_l.setSpacing(2)

        for i, opt in enumerate(self._options):
            btn = QPushButton(f"  {opt}")
            btn.setFixedHeight(46)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            is_sel = (i == self._selected)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(249,115,22,0.30)' if is_sel else 'transparent'};
                    border: {'2px solid rgba(249,115,22,0.7)' if is_sel else '1px solid transparent'};
                    border-radius: 10px;
                    color: {'#FFFFFF' if is_sel else '#E0F2FE'};
                    font-size: 14px;
                    font-weight: {'800' if is_sel else '600'};
                    text-align: left;
                    padding: 0 12px;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.15);
                    border: 1px solid {BORDER_HOV};
                    color: #FFFFFF;
                }}
            """)
            btn.clicked.connect(lambda _, idx=i: self._select(idx))
            inner_l.addWidget(btn)

        scroll.setWidget(inner)
        pop_l.addWidget(scroll)

        # Size: cap at 5 items visible, then scroll
        item_h   = 48 + 2
        visible  = min(len(self._options), 5)
        pop_h    = visible * item_h + 18
        pop_w    = self._btn.width()

        # Position below the button
        pos = self._btn.mapToGlobal(self._btn.rect().bottomLeft())
        self._popup.setFixedSize(pop_w, pop_h)
        self._popup.move(pos)
        self._popup.show()

    def _select(self, idx: int):
        self._selected = idx
        self._update_btn()
        if self._popup:
            self._popup.hide()
        self.changed.emit(idx)

    def current_index(self) -> int:
        return self._selected


# ── Setting toggle (on/off button) ────────────────────────────────────────────
class SettingToggle(QWidget):
    """A labelled on/off toggle button."""
    changed = pyqtSignal(bool)

    def __init__(self, label: str, default: bool = False, parent=None):
        super().__init__(parent)
        self._value = default
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"""
            color: {TEXT_LIGHT}; font-size: 14px;
            font-weight: 900; letter-spacing: 2px;
            background: transparent;
        """)
        root.addWidget(lbl)

        self._btn = QPushButton()
        self._btn.setFixedHeight(78)
        self._btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn.clicked.connect(self._toggle)
        self._update_btn()
        root.addWidget(self._btn)

    def _toggle(self):
        self._value = not self._value
        self._update_btn()
        self.changed.emit(self._value)

    def _update_btn(self):
        if self._value:
            self._btn.setText("  ON  ✓")
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(34,197,94,0.30);
                    border: 2px solid rgba(34,197,94,0.80);
                    border-radius: 14px;
                    color: #FFFFFF;
                    font-size: 18px;
                    font-weight: 800;
                    text-align: left;
                    padding: 0 16px;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: rgba(34,197,94,0.45);
                }}
            """)
        else:
            self._btn.setText("  OFF")
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.08);
                    border: 2px solid {BORDER};
                    border-radius: 14px;
                    color: {TEXT_DIM};
                    font-size: 18px;
                    font-weight: 700;
                    text-align: left;
                    padding: 0 16px;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.15);
                    border: 2px solid {BORDER_HOV};
                }}
            """)

    def value(self) -> bool:
        return self._value


# ── Lobby screen ──────────────────────────────────────────────────────────────
class LobbyScreen(QWidget):
    start_requested = pyqtSignal(dict)  # emits game_settings dict
    back_requested  = pyqtSignal()

    # ── Default settings ──────────────────────────────────────────────────────
    _TIME_PRESETS = [
        ("Fast",          1 * 60),
        ("Normal",        3 * 60),
        ("Slow",          5 * 60),
        ("Art-work",     10 * 60),
        ("Infinite",          0),   # 0 = no timer
        ("Host's Choice",    -1),   # -1 = show custom input
    ]
    _TURN_PRESETS = [
        ("Few",    2),
        ("Normal", 3),
        ("Story",  5),
        ("Movie",  10),
        ("Until host stops", -1),
    ]
    _FLOW_PRESETS = [
        ("Write → Draw",   "write_draw"),
        ("Draw → Write",   "draw_write"),
        ("Only Drawing",   "draw_only"),
        ("Only Writing",   "write_only"),
    ]

    def __init__(self, is_host: bool = True, room_code: str = "4821",
                 max_players: int = 8, require_code: bool = True, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        self._is_host      = is_host
        self._room_code    = room_code
        self._max_players  = max_players
        self._require_code = require_code
        self._players      = []

        # Settings state
        self._time_idx        = 1      # Normal (3 min)
        self._turn_idx        = 1      # Normal (3 turns)
        self._flow_idx        = 0      # Write → Draw
        self._custom_time     = 3      # minutes, used when Host's Choice selected
        # Game controls
        self._submit_once     = False  # Submit Only Once toggle
        self._panic_mode      = True   # Panic Mode toggle
        self._panic_secs      = 15     # Panic Mode activation (seconds)
        # Result settings
        self._result_pacing_idx   = 1  # Normal
        self._host_result_control = False  # Host Control Over Results

        self._build_ui()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Main content (left + right panels) ────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._content_layout = QHBoxLayout(content)
        self._content_layout.setSpacing(16)
        self._content_layout.setContentsMargins(24, 24, 24, 12)

        self._content_layout.addWidget(self._build_left_panel(),  stretch=2)
        self._content_layout.addWidget(self._build_right_panel(), stretch=3)

        root.addWidget(content, stretch=1)

        # ── Bottom bar ─────────────────────────────────────────────────────
        root.addWidget(self._build_bottom_bar())

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"""
            QWidget#leftPanel {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
        """)
        panel.setObjectName("leftPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(10)

        # Header
        self._player_count_lbl = QLabel(f"PLAYERS  {len(self._players)} / {self._max_players}")
        self._player_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._player_count_lbl.setStyleSheet(f"""
            color: {ORANGE};
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 2px;
        """)
        layout.addWidget(self._player_count_lbl)
        layout.addWidget(make_divider())

        # Scrollable slot list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.08);
                width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.35);
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._slots_widget = QWidget()
        self._slots_widget.setStyleSheet("background: transparent;")
        self._slots_layout = QVBoxLayout(self._slots_widget)
        self._slots_layout.setContentsMargins(0, 0, 0, 0)
        self._slots_layout.setSpacing(6)
        self._slots_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._refresh_slots()

        scroll.setWidget(self._slots_widget)
        layout.addWidget(scroll, stretch=1)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"""
            QWidget#rightPanel {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
        """)
        panel.setObjectName("rightPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Scrollable inner content ───────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.08);
                width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.35); border-radius: 3px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        header = QLabel("ROOM SETTINGS")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"""
            color: {TEXT_LIGHT}; font-size: 16px;
            font-weight: 900; letter-spacing: 3px;
            background: transparent;
        """)
        layout.addWidget(header)
        layout.addSpacing(10)
        layout.addWidget(make_divider())
        layout.addSpacing(10)

        # ── Locked rows ────────────────────────────────────────────────────
        code_val = self._room_code if self._require_code else "None"
        layout.addWidget(self._locked_row("Max Players", str(self._max_players)))
        layout.addSpacing(6)
        layout.addWidget(make_divider())
        layout.addSpacing(6)
        layout.addWidget(self._locked_row("Room Code", code_val))
        layout.addSpacing(6)
        layout.addWidget(make_divider())
        layout.addSpacing(14)

        if self._is_host:
            # ── TIME dropdown ──────────────────────────────────────────────
            time_labels = [
                f"{name}  ({self._fmt_time(secs)})" if secs >= 0
                else f"{name}  (∞)" if secs == 0
                else name
                for name, secs in self._TIME_PRESETS
            ]
            self._time_dd = SettingDropdown(
                "⏱  TIME PER ROUND",
                time_labels,
                self._time_idx,
                self
            )
            self._time_dd.changed.connect(self._on_time)
            layout.addWidget(self._time_dd)
            layout.addSpacing(8)

            # Custom time input (hidden unless Host's Choice)
            self._custom_time_row = QWidget()
            self._custom_time_row.setStyleSheet("background: transparent;")
            ct_l = QHBoxLayout(self._custom_time_row)
            ct_l.setContentsMargins(8, 0, 0, 0)
            ct_l.setSpacing(10)
            ct_lbl = QLabel("Enter minutes:")
            ct_lbl.setStyleSheet(
                f"color:{TEXT_DIM}; font-size:14px; font-weight:600; background:transparent;")
            self._custom_time_input = QLineEdit(str(self._custom_time))
            self._custom_time_input.setFixedWidth(90)
            self._custom_time_input.setFixedHeight(38)
            self._custom_time_input.setMaxLength(3)
            self._custom_time_input.setStyleSheet(f"""
                QLineEdit {{
                    background: rgba(255,255,255,0.15);
                    border: 2px solid {BORDER};
                    border-radius: 12px;
                    color: {TEXT_LIGHT};
                    font-size: 15px;
                    font-weight: 700;
                    padding: 0 12px;
                }}
                QLineEdit:focus {{ border: 2px solid {BORDER_HOV}; }}
            """)
            self._custom_time_input.textChanged.connect(
                lambda t: setattr(self, '_custom_time', int(t) if t.isdigit() else 1))
            ct_l.addWidget(ct_lbl)
            ct_l.addWidget(self._custom_time_input)
            ct_l.addStretch()
            self._custom_time_row.setVisible(self._time_idx == len(self._TIME_PRESETS) - 1)
            layout.addWidget(self._custom_time_row)

            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(8)

            # ── TURNS dropdown ─────────────────────────────────────────────
            turn_labels = [
                f"{name}  ({n} turns)" if n > 0 else name
                for name, n in self._TURN_PRESETS
            ]
            self._turn_dd = SettingDropdown(
                "🔄  TURNS  (write + draw = 1 turn)",
                turn_labels,
                self._turn_idx,
                self
            )
            self._turn_dd.changed.connect(self._on_turn)
            layout.addWidget(self._turn_dd)
            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(8)

            # ── TASK FLOW dropdown ─────────────────────────────────────────
            self._flow_dd = SettingDropdown(
                "🔀  TASK FLOW",
                [name for name, _ in self._FLOW_PRESETS],
                self._flow_idx,
                self
            )
            self._flow_dd.changed.connect(self._on_flow)
            layout.addWidget(self._flow_dd)
            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(8)

            # ── SUBMIT ONLY ONCE toggle ────────────────────────────────────
            self._submit_once_toggle = SettingToggle(
                "SUBMIT ONLY ONCE", default=self._submit_once)
            self._submit_once_toggle.changed.connect(
                lambda v: setattr(self, '_submit_once', v))
            layout.addWidget(self._submit_once_toggle)
            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(8)

            # ── PANIC MODE toggle ──────────────────────────────────────────
            self._panic_toggle = SettingToggle(
                "PANIC MODE", default=self._panic_mode)
            self._panic_toggle.changed.connect(self._on_panic_toggle)
            layout.addWidget(self._panic_toggle)
            layout.addSpacing(6)

            # Panic activation input (visible when panic mode on)
            self._panic_row = QWidget()
            self._panic_row.setStyleSheet("background: transparent;")
            pr_l = QHBoxLayout(self._panic_row)
            pr_l.setContentsMargins(8, 0, 0, 0)
            pr_l.setSpacing(10)
            pr_lbl = QLabel("Activate at (seconds):")
            pr_lbl.setStyleSheet(
                f"color:{TEXT_DIM}; font-size:14px; font-weight:600; background:transparent;")
            self._panic_input = QLineEdit(str(self._panic_secs))
            self._panic_input.setFixedWidth(80)
            self._panic_input.setFixedHeight(38)
            self._panic_input.setMaxLength(3)
            self._panic_input.setStyleSheet(f"""
                QLineEdit {{
                    background: rgba(255,255,255,0.15);
                    border: 2px solid {BORDER};
                    border-radius: 12px;
                    color: {TEXT_LIGHT};
                    font-size: 15px; font-weight: 700;
                    padding: 0 12px;
                }}
                QLineEdit:focus {{ border: 2px solid {BORDER_HOV}; }}
            """)
            self._panic_input.textChanged.connect(
                lambda t: setattr(self, '_panic_secs', int(t) if t.isdigit() else 15))
            pr_l.addWidget(pr_lbl)
            pr_l.addWidget(self._panic_input)
            pr_l.addStretch()
            self._panic_row.setVisible(self._panic_mode)
            layout.addWidget(self._panic_row)
            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(8)

            # ── RESULT PACING dropdown ─────────────────────────────────────
            _PACING = [
                "Fast  (0.06s/letter | 3s/drawing)",
                "Normal  (0.13s/letter | 5s/drawing)",
                "Slow  (0.25s/letter | 10s/drawing)",
                "Custom",
            ]
            self._pacing_dd = SettingDropdown(
                "RESULT PACING", _PACING, self._result_pacing_idx, self)
            self._pacing_dd.changed.connect(self._on_pacing)
            layout.addWidget(self._pacing_dd)
            layout.addSpacing(6)

            # Custom pacing inputs (hidden unless Custom selected)
            self._custom_pacing_row = QWidget()
            self._custom_pacing_row.setStyleSheet("background: transparent;")
            cp_l = QHBoxLayout(self._custom_pacing_row)
            cp_l.setContentsMargins(8, 0, 0, 0)
            cp_l.setSpacing(8)
            self._custom_letter_s = QLineEdit("0.13")
            self._custom_drawing_s = QLineEdit("5")
            for inp, placeholder in [(self._custom_letter_s, "s/letter"),
                                      (self._custom_drawing_s, "s/drawing")]:
                inp.setFixedWidth(75)
                inp.setFixedHeight(36)
                inp.setMaxLength(6)
                inp.setStyleSheet(f"""
                    QLineEdit {{
                        background: rgba(255,255,255,0.15);
                        border: 2px solid {BORDER}; border-radius: 10px;
                        color: {TEXT_LIGHT}; font-size: 14px;
                        font-weight: 700; padding: 0 8px;
                    }}
                    QLineEdit:focus {{ border: 2px solid {BORDER_HOV}; }}
                """)
                lbl = QLabel(placeholder)
                lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:12px; background:transparent;")
                cp_l.addWidget(inp)
                cp_l.addWidget(lbl)
            cp_l.addStretch()
            self._custom_pacing_row.setVisible(False)
            layout.addWidget(self._custom_pacing_row)
            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(8)

            # ── HOST CONTROL OVER RESULTS toggle ──────────────────────────
            self._host_result_toggle = SettingToggle(
                "HOST CONTROL OVER RESULTS", default=self._host_result_control)
            self._host_result_toggle.changed.connect(
                lambda v: setattr(self, '_host_result_control', v))
            layout.addWidget(self._host_result_toggle)

        else:
            layout.addWidget(self._locked_row("Time",      self._fmt_time_idx(self._time_idx)))
            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(6)
            layout.addWidget(self._locked_row("Turns",     self._TURN_PRESETS[self._turn_idx][0]))
            layout.addSpacing(6)
            layout.addWidget(make_divider())
            layout.addSpacing(6)
            layout.addWidget(self._locked_row("Task Flow", self._FLOW_PRESETS[self._flow_idx][0]))

        layout.addStretch()

        if not self._is_host:
            waiting = QLabel("Waiting for the host to start…")
            waiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
            waiting.setStyleSheet(f"""
                color: {TEXT_DIM}; font-size: 13px;
                font-weight: 600; letter-spacing: 1px; background: transparent;
            """)
            layout.addWidget(waiting)

        scroll.setWidget(inner)
        panel.layout().addWidget(scroll)
        return panel

    # ── Settings helpers ──────────────────────────────────────────────────────

    def _locked_row(self, label: str, value: str) -> QWidget:
        """Read-only setting row — bigger than before."""
        row = QWidget()
        row.setFixedHeight(54)
        row.setStyleSheet("background: transparent; border: none;")
        l = QHBoxLayout(row)
        l.setContentsMargins(4, 0, 4, 0)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:15px; font-weight:700; background:transparent;")
        val = QLabel(value)
        val.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:15px; font-weight:800; background:transparent;")
        l.addWidget(lbl, stretch=1)
        l.addWidget(val)
        return row

    def _on_time(self, idx: int):
        self._time_idx = idx
        if hasattr(self, "_custom_time_row"):
            self._custom_time_row.setVisible(idx == len(self._TIME_PRESETS) - 1)

    def _on_turn(self, idx: int):
        self._turn_idx = idx

    def _on_flow(self, idx: int):
        self._flow_idx = idx

    def _fmt_time(self, secs: int) -> str:
        if secs == 0:  return "∞"
        if secs < 60:  return f"{secs}s"
        return f"{secs // 60}m"

    def _fmt_time_idx(self, idx: int) -> str:
        name, secs = self._TIME_PRESETS[idx]
        if secs == -1: return f"{name}  ({self._custom_time}m)"
        return f"{name}  ({self._fmt_time(secs)})"

    def _on_panic_toggle(self, v: bool):
        self._panic_mode = v
        if hasattr(self, "_panic_row"):
            self._panic_row.setVisible(v)

    def _on_pacing(self, idx: int):
        self._result_pacing_idx = idx
        if hasattr(self, "_custom_pacing_row"):
            self._custom_pacing_row.setVisible(idx == 3)

    def get_game_settings(self) -> dict:
        name_t, secs = self._TIME_PRESETS[self._time_idx]
        if secs == -1:
            secs = self._custom_time * 60
        name_n, turns = self._TURN_PRESETS[self._turn_idx]
        name_f, flow  = self._FLOW_PRESETS[self._flow_idx]

        # Result pacing values
        _PACING_VALUES = [
            (0.0625, 3.0),
            (0.125,  5.0),
            (0.25,  10.0),
        ]
        if self._result_pacing_idx < 3:
            letter_s, drawing_s = _PACING_VALUES[self._result_pacing_idx]
        else:
            try:
                letter_s  = float(self._custom_letter_s.text())
                drawing_s = float(self._custom_drawing_s.text())
            except Exception:
                letter_s, drawing_s = 0.125, 5.0

        return {
            "time_label":          name_t,
            "time_secs":           secs,
            "turns_label":         name_n,
            "turns":               turns,
            "flow_label":          name_f,
            "flow":                flow,
            "submit_once":         self._submit_once,
            "panic_mode":          self._panic_mode,
            "panic_secs":          self._panic_secs,
            "result_letter_secs":  letter_s,
            "result_drawing_secs": drawing_s,
            "host_result_control": self._host_result_control,
        }


    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(80)
        bar.setStyleSheet("background: rgba(0,0,0,0.18); border: none;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(14)

        # ── Back button — red circle with ← ───────────────────────────────
        back_btn = QPushButton("←")
        back_btn.setFixedSize(52, 52)
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.clicked.connect(self.back_requested)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,68,68,0.75);
                border: 2px solid rgba(239,68,68,0.4);
                border-radius: 26px;
                color: {TEXT_LIGHT};
                font-size: 22px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: rgba(239,68,68,0.95);
                border: 2px solid rgba(239,68,68,0.7);
            }}
        """)
        layout.addWidget(back_btn)

        # ── Host IP box ───────────────────────────────────────────────────
        if self._is_host:
            ip_box = QWidget()
            ip_box.setObjectName("ipBox")
            ip_box.setStyleSheet(f"""
                QWidget#ipBox {{
                    background: rgba(255,255,255,0.12);
                    border: 1px solid {BORDER};
                    border-radius: 26px;
                }}
                QWidget#ipBox QLabel {{
                    background: transparent;
                    border: none;
                    border-radius: 0px;
                }}
            """)
            ip_layout = QHBoxLayout(ip_box)
            ip_layout.setContentsMargins(18, 0, 8, 0)
            ip_layout.setSpacing(8)

            ip_title = QLabel("YOUR IP")
            ip_title.setStyleSheet(f"""
                color: {TEXT_DIM};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 2px;
            """)

            self._ip_label = QLabel("—")
            self._ip_label.setStyleSheet(f"""
                color: {TEXT_LIGHT};
                font-size: 15px;
                font-weight: 900;
                letter-spacing: 2px;
            """)
            self._ip_visible = False
            self._ip_real    = "—"

            def _masked(ip: str) -> str:
                return "●●●.●●●.●●●.●●●"

            eye_btn = QPushButton("🙈")
            eye_btn.setFixedSize(38, 38)
            eye_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            eye_btn.setToolTip("Show / hide IP")
            eye_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.15);
                    border: 1px solid {BORDER};
                    border-radius: 19px;
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.28);
                    border: 1px solid {BORDER_HOV};
                }}
            """)

            ip_copy_btn = QPushButton("⧉")
            ip_copy_btn.setFixedSize(38, 38)
            ip_copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            ip_copy_btn.setToolTip("Copy IP")
            ip_copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.15);
                    border: 1px solid {BORDER};
                    border-radius: 19px;
                    color: {TEXT_LIGHT};
                    font-size: 16px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.28);
                    border: 1px solid {BORDER_HOV};
                }}
            """)

            def toggle_ip():
                self._ip_visible = not self._ip_visible
                if self._ip_visible:
                    self._ip_label.setText(self._ip_real)
                    eye_btn.setText("🙉")
                else:
                    self._ip_label.setText(_masked(self._ip_real))
                    eye_btn.setText("🙈")

            def copy_ip():
                from PyQt6.QtCore import QTimer
                QApplication.clipboard().setText(self._ip_real)
                ip_copy_btn.setText("✓")
                QTimer.singleShot(1500, lambda: ip_copy_btn.setText("⧉"))

            eye_btn.clicked.connect(toggle_ip)
            ip_copy_btn.clicked.connect(copy_ip)

            # Start hidden
            self._ip_label.setText(_masked("—"))

            ip_layout.addWidget(ip_title)
            ip_layout.addWidget(self._ip_label)
            ip_layout.addStretch()
            ip_layout.addWidget(eye_btn)
            ip_layout.addWidget(ip_copy_btn)
            layout.addWidget(ip_box, stretch=1)

        # ── Room code box ─────────────────────────────────────────────────
        if self._require_code:
            code_box = QWidget()
            code_box.setObjectName("codeBox")
            code_box.setStyleSheet(f"""
                QWidget#codeBox {{
                    background: rgba(255,255,255,0.12);
                    border: 1px solid {BORDER};
                    border-radius: 26px;
                }}
                QWidget#codeBox QLabel {{
                    background: transparent;
                    border: none;
                    border-radius: 0px;
                }}
            """)
            box_layout = QHBoxLayout(code_box)
            box_layout.setContentsMargins(18, 0, 8, 0)
            box_layout.setSpacing(10)

            code_label = QLabel("ROOM CODE")
            code_label.setStyleSheet(f"""
                color: {TEXT_DIM};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 2px;
            """)

            code_value = QLabel(self._room_code)
            code_value.setStyleSheet(f"""
                color: {TEXT_LIGHT};
                font-size: 18px;
                font-weight: 900;
                letter-spacing: 5px;
            """)

            copy_btn = QPushButton("⧉")
            copy_btn.setFixedSize(38, 38)
            copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            copy_btn.setToolTip("Copy room code")
            copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.15);
                    border: 1px solid {BORDER};
                    border-radius: 19px;
                    color: {TEXT_LIGHT};
                    font-size: 16px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.28);
                    border: 1px solid {BORDER_HOV};
                }}
            """)

            def copy_code():
                from PyQt6.QtCore import QTimer
                QApplication.clipboard().setText(self._room_code)
                copy_btn.setText("✓")
                QTimer.singleShot(1500, lambda: copy_btn.setText("⧉"))

            copy_btn.clicked.connect(copy_code)

            box_layout.addWidget(code_label)
            box_layout.addWidget(code_value)
            box_layout.addStretch()
            box_layout.addWidget(copy_btn)
            layout.addWidget(code_box, stretch=1)
        else:
            layout.addStretch(1)

        # ── Start button — orange circle with ▶ (host only) ───────────────
        if self._is_host:
            self._start_btn = QPushButton("▶")
            self._start_btn.setFixedSize(52, 52)
            self._start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._start_btn.clicked.connect(lambda: self.start_requested.emit(self.get_game_settings()))
            self._apply_start_style(False)
            self._start_btn.enterEvent = lambda e: self._apply_start_style(True)
            self._start_btn.leaveEvent = lambda e: self._apply_start_style(False)
            layout.addWidget(self._start_btn)
        else:
            layout.addStretch()

        return bar

    # ── Slot refresh ──────────────────────────────────────────────────────────

    def _refresh_slots(self):
        # Clear existing
        while self._slots_layout.count():
            item = self._slots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Filled slots
        for player in self._players:
            slot = PlayerSlot(
                username=player["username"],
                is_host=player["is_host"],
                pixmap=player.get("pixmap"),
                empty=False
            )
            self._slots_layout.addWidget(slot)

        # Empty slots
        empty_count = self._max_players - len(self._players)
        for _ in range(empty_count):
            self._slots_layout.addWidget(PlayerSlot(empty=True))

        # Update count label
        self._player_count_lbl.setText(
            f"PLAYERS  {len(self._players)} / {self._max_players}"
        )

    # ── Public API (called by window.py when server sends updates) ────────────

    def add_player(self, username: str, is_host: bool = False, pixmap: QPixmap = None):
        self._players.append({"username": username, "is_host": is_host, "pixmap": pixmap})
        self._refresh_slots()

    def remove_player(self, username: str):
        self._players = [p for p in self._players if p["username"] != username]
        self._refresh_slots()

    def set_host_ip(self, ip: str):
        if hasattr(self, "_ip_label"):
            self._ip_real = ip
            if not self._ip_visible:
                self._ip_label.setText("●●●.●●●.●●●.●●●")
            else:
                self._ip_label.setText(ip)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _apply_start_style(self, hovered: bool):
        bg = ORANGE_HOV if hovered else ORANGE
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: 3px solid rgba(249,115,22,0.4);
                border-radius: 26px;
                color: #FFFFFF;
                font-size: 22px;
                font-weight: 800;
            }}
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        pad = max(16, int(self.width() * 0.028))
        self._content_layout.setContentsMargins(pad, pad, pad, pad // 2)


if __name__ == "__main__":
    from PyQt6.QtCore import QTimer
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = QMainWindow()
    w.setMinimumSize(600, 420)
    w.resize(860, 580)
    screen = LobbyScreen(is_host=True, room_code="4821", max_players=8, require_code=True)
    screen.add_player("Noam", is_host=True)
    w.setCentralWidget(screen)
    screen.start_requested.connect(lambda: print("→ Start game"))
    screen.back_requested.connect(lambda: print("← Back"))
    QTimer.singleShot(1000, lambda: screen.add_player("TestBot"))
    QTimer.singleShot(2000, lambda: screen.add_player("Player3"))
    w.show()
    sys.exit(app.exec())