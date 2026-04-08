"""
Server Browser — shows all open lobby rooms on the Render server.
Players can click a room to join, or type a code directly.
"""
import base64
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QByteArray, QTimer
from PyQt6.QtGui import QPixmap, QCursor, QColor, QPainter, QPainterPath, QBrush

BG        = "#0EA5E9"
PANEL_BG  = "rgba(0,0,0,0.18)"
BORDER    = "rgba(255,255,255,0.35)"
BORDER_H  = "rgba(255,255,255,0.85)"
TEXT      = "#FFFFFF"
DIM       = "#E0F2FE"
GHOST     = "rgba(255,255,255,0.45)"
ORANGE    = "#F97316"
ORANGE_H  = "#FB923C"
GREEN     = "rgba(34,197,94,0.85)"
GREEN_H   = "rgba(34,197,94,1.0)"
YELLOW    = "rgba(234,179,8,0.85)"
YELLOW_H  = "rgba(234,179,8,1.0)"
RED       = "rgba(239,68,68,0.80)"


def _b64_to_pixmap(b64: str) -> QPixmap:
    try:
        px = QPixmap()
        px.loadFromData(QByteArray(base64.b64decode(b64)))
        return px
    except Exception:
        return QPixmap()


def _circular_avatar(b64: str, size: int) -> QLabel:
    lbl = QLabel(); lbl.setFixedSize(size, size)
    lbl.setStyleSheet("background:transparent;")
    px  = _b64_to_pixmap(b64) if b64 else QPixmap()
    out = QPixmap(size, size); out.fill(Qt.GlobalColor.transparent)
    p   = QPainter(out); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(); path.addEllipse(0, 0, size, size); p.setClipPath(path)
    if px.isNull():
        p.setBrush(QBrush(QColor("#0369A1"))); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, size, size)
    else:
        scaled = px.scaled(size, size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((size-scaled.width())//2, (size-scaled.height())//2, scaled)
    p.end(); lbl.setPixmap(out); return lbl


class RoomCard(QWidget):
    join_clicked = pyqtSignal(str, bool)   # code, requires_code

    def __init__(self, room: dict, parent=None):
        super().__init__(parent)
        self._room = room
        self._build()

    def _build(self):
        code          = self._room.get("code", "")
        host_name     = self._room.get("host_username", "?")
        host_avatar   = self._room.get("host_avatar", "")
        country       = self._room.get("country", "")
        player_count  = self._room.get("player_count", 1)
        max_players   = self._room.get("max_players", 8)
        requires_code = self._room.get("requires_code", False)

        self.setStyleSheet(f"""
            QWidget {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
        """)
        self.setFixedHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(14)

        # Left — avatar + info
        av = _circular_avatar(host_avatar, 52)
        row.addWidget(av, alignment=Qt.AlignmentFlag.AlignVCenter)

        info = QVBoxLayout(); info.setSpacing(2); info.setContentsMargins(0,0,0,0)
        name_lbl = QLabel(host_name)
        name_lbl.setStyleSheet(f"color:{TEXT};font-size:17px;font-weight:800;background:transparent;")
        info.addWidget(name_lbl)
        if country:
            loc_lbl = QLabel(country)
            loc_lbl.setStyleSheet(f"color:{DIM};font-size:13px;font-weight:600;background:transparent;")
            info.addWidget(loc_lbl)
        row.addLayout(info, stretch=1)

        # Right — join button + player count
        right = QVBoxLayout(); right.setSpacing(4); right.setContentsMargins(0,0,0,0)
        right.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        join_btn = QPushButton("🔒  JOIN" if requires_code else "JOIN")
        join_btn.setFixedSize(120, 40)
        join_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        color    = GREEN   if requires_code else YELLOW
        color_h  = GREEN_H if requires_code else YELLOW_H
        join_btn.setStyleSheet(f"""
            QPushButton {{
                background:{color};border:none;border-radius:12px;
                color:#FFFFFF;font-size:14px;font-weight:800;letter-spacing:1px;
            }}
            QPushButton:hover{{background:{color_h};}}
        """)
        join_btn.clicked.connect(lambda: self.join_clicked.emit(code, requires_code))
        right.addWidget(join_btn, alignment=Qt.AlignmentFlag.AlignRight)

        full = player_count >= max_players
        count_lbl = QLabel(f"{player_count} / {max_players}" + (" · FULL" if full else ""))
        count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        count_lbl.setStyleSheet(
            f"color:{'#F87171' if full else GHOST};font-size:12px;font-weight:700;background:transparent;")
        right.addWidget(count_lbl, alignment=Qt.AlignmentFlag.AlignRight)
        row.addLayout(right)


class ServerBrowserScreen(QWidget):
    # Emits (code, requires_code) when player picks a room
    join_requested  = pyqtSignal(str, bool)
    # Emits when player types a code directly
    code_join       = pyqtSignal(str)
    back_requested  = pyqtSignal()
    refresh_needed  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        self._build()

    def _build(self):
        try:
            from app import scale as ui_scale; S = ui_scale.get()
        except ImportError: S = 1.0
        self._S = S

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        pad = QWidget(); pad.setStyleSheet("background:transparent;")
        pad_l = QVBoxLayout(pad)
        pad_l.setContentsMargins(int(40*S), int(24*S), int(40*S), int(24*S))
        pad_l.setSpacing(int(16*S))

        # ── Header ────────────────────────────────────────────────────────
        header_row = QHBoxLayout(); header_row.setContentsMargins(0,0,0,0)

        back_btn = QPushButton("← BACK")
        back_btn.setFixedHeight(int(48*S))
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.clicked.connect(self.back_requested)
        back_btn.setStyleSheet(f"""
            QPushButton{{background:{RED};border:none;border-radius:{int(14*S)}px;
            color:#FFF;font-size:{int(14*S)}px;font-weight:800;padding:0 {int(20*S)}px;}}
            QPushButton:hover{{background:rgba(239,68,68,0.95);}}
        """)

        title = QLabel("OPEN SERVERS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:#FFFFFF;font-size:{int(22*S)}px;font-weight:900;letter-spacing:3px;background:transparent;")

        self._refresh_btn = QPushButton("↻  REFRESH")
        self._refresh_btn.setFixedHeight(int(48*S))
        self._refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton{{background:rgba(255,255,255,0.15);border:1px solid {BORDER};
            border-radius:{int(14*S)}px;color:#FFF;font-size:{int(14*S)}px;
            font-weight:700;padding:0 {int(20*S)}px;}}
            QPushButton:hover{{background:rgba(255,255,255,0.25);}}
        """)

        header_row.addWidget(back_btn)
        header_row.addWidget(title, stretch=1)
        header_row.addWidget(self._refresh_btn)
        pad_l.addLayout(header_row)

        # ── Room list scroll ───────────────────────────────────────────────
        card = QWidget(); card.setObjectName("SB")
        card.setStyleSheet(f"QWidget#SB{{background:{PANEL_BG};border:1px solid {BORDER};border-radius:20px;}}")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_l = QVBoxLayout(card); card_l.setContentsMargins(0,0,0,0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea{background:transparent;border:none;}
            QScrollBar:vertical{background:rgba(255,255,255,0.08);width:6px;border-radius:3px;}
            QScrollBar::handle:vertical{background:rgba(255,255,255,0.35);border-radius:3px;min-height:20px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        """)

        self._list_widget = QWidget(); self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(int(16*S), int(16*S), int(16*S), int(16*S))
        self._list_layout.setSpacing(int(10*S))
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._status_lbl = QLabel("Searching for servers...")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(f"color:{DIM};font-size:16px;font-weight:600;background:transparent;")
        self._list_layout.addWidget(self._status_lbl)

        self._scroll.setWidget(self._list_widget)
        card_l.addWidget(self._scroll)
        pad_l.addWidget(card, stretch=1)

        # ── Bottom — direct code entry ─────────────────────────────────────
        bottom = QWidget()
        bottom.setStyleSheet(f"QWidget{{background:{PANEL_BG};border:1px solid {BORDER};border-radius:16px;}}")
        bottom.setFixedHeight(int(80*S))
        bl = QHBoxLayout(bottom); bl.setContentsMargins(int(20*S), 0, int(20*S), 0); bl.setSpacing(int(12*S))

        code_lbl = QLabel("Have a code?")
        code_lbl.setStyleSheet(f"color:{DIM};font-size:{int(14*S)}px;font-weight:700;background:transparent;")
        bl.addWidget(code_lbl)

        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("Enter room code...")
        self._code_input.setMaxLength(6)
        self._code_input.setFixedHeight(int(44*S))
        self._code_input.setStyleSheet(f"""
            QLineEdit{{background:rgba(255,255,255,0.15);border:2px solid {BORDER};
            border-radius:{int(12*S)}px;color:#FFF;font-size:{int(16*S)}px;
            font-weight:700;padding:0 {int(14*S)}px;letter-spacing:2px;}}
            QLineEdit:focus{{border:2px solid {BORDER_H};}}
        """)
        self._code_input.returnPressed.connect(self._on_code_join)
        bl.addWidget(self._code_input, stretch=1)

        go_btn = QPushButton("JOIN  ▶")
        go_btn.setFixedHeight(int(44*S))
        go_btn.setFixedWidth(int(120*S))
        go_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        go_btn.clicked.connect(self._on_code_join)
        go_btn.setStyleSheet(f"""
            QPushButton{{background:{ORANGE};border:none;border-radius:{int(12*S)}px;
            color:#FFF;font-size:{int(15*S)}px;font-weight:800;}}
            QPushButton:hover{{background:{ORANGE_H};}}
        """)
        bl.addWidget(go_btn)
        pad_l.addWidget(bottom)

        root.addWidget(pad)

    def update_rooms(self, rooms: list):
        """Called when server sends room list."""
        # Clear existing
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not rooms:
            lbl = QLabel("No open servers found.\nCreate a room to get started!")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{DIM};font-size:16px;font-weight:600;background:transparent;")
            self._list_layout.addWidget(lbl)
            return

        for room in rooms:
            if room.get("player_count", 0) >= room.get("max_players", 8):
                continue   # skip full rooms
            card = RoomCard(room)
            card.join_clicked.connect(self.join_requested)
            self._list_layout.addWidget(card)

        if self._list_layout.count() == 0:
            lbl = QLabel("All servers are currently full.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{DIM};font-size:16px;background:transparent;")
            self._list_layout.addWidget(lbl)

    def set_status(self, text: str):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._status_lbl = QLabel(text)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(f"color:{DIM};font-size:16px;font-weight:600;background:transparent;")
        self._list_layout.addWidget(self._status_lbl)

    def _on_refresh(self):
        self.set_status("Refreshing...")
        self.refresh_needed.emit()

    def _on_code_join(self):
        code = self._code_input.text().strip().upper()
        if code:
            self.code_join.emit(code)