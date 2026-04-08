import os, base64
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QByteArray, QTimer,
    QPropertyAnimation, QEasingCurve,
    QSequentialAnimationGroup, QParallelAnimationGroup
)
from PyQt6.QtGui import QColor, QPixmap, QCursor, QPainter, QPen, QBrush, QPainterPath, QFont

PANEL_BG  = "rgba(0,0,0,0.18)"
BORDER    = "rgba(255,255,255,0.35)"
TEXT      = "#FFFFFF"
DIM       = "#E0F2FE"
GHOST     = "rgba(255,255,255,0.35)"
ORANGE    = "#F97316"
ORANGE_H  = "#FB923C"
GOLD      = "#FBBF24"
GOLD_GLOW = "rgba(251,191,36,0.25)"
MSG_RIGHT = "rgba(249,115,22,0.25)"   # sender bubble (sentences)
MSG_LEFT  = "rgba(255,255,255,0.10)"  # receiver bubble (drawings)


def _div():
    d = QFrame(); d.setFrameShape(QFrame.Shape.HLine)
    d.setStyleSheet(f"background:{BORDER};max-height:1px;border:none;"); return d


def _b64_to_pixmap(b64: str) -> QPixmap:
    try:
        px = QPixmap(); px.loadFromData(QByteArray(base64.b64decode(b64))); return px
    except Exception: return QPixmap()


def _make_avatar(b64: str, size: int) -> QLabel:
    """Circular avatar label."""
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet("background:transparent;")
    px  = _b64_to_pixmap(b64) if b64 else QPixmap()
    out = QPixmap(size, size); out.fill(Qt.GlobalColor.transparent)
    p   = QPainter(out); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(); path.addEllipse(0, 0, size, size); p.setClipPath(path)
    if px.isNull():
        p.setBrush(QBrush(QColor("#0369A1"))); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, size, size)
    else:
        scaled = px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((size-scaled.width())//2, (size-scaled.height())//2, scaled)
    p.end(); lbl.setPixmap(out); return lbl


# ── Black overlay ─────────────────────────────────────────────────────────────
class BlackOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background:#000000;")
        self._fx = QGraphicsOpacityEffect(self); self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx); self.hide()

    def fade_to(self, target, duration) -> QPropertyAnimation:
        self.show(); self.raise_()
        a = QPropertyAnimation(self._fx, b"opacity")
        a.setDuration(duration); a.setStartValue(self._fx.opacity())
        a.setEndValue(target); a.setEasingCurve(QEasingCurve.Type.InOutQuad); return a

    def opacity(self): return self._fx.opacity()


# ── Player tab (left panel) ───────────────────────────────────────────────────
class PlayerTab(QWidget):
    clicked = pyqtSignal()
    def __init__(self, username, avatar_b64="", active=False, parent=None):
        super().__init__(parent)
        self._active = active; self._clickable = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        l = QHBoxLayout(self); l.setContentsMargins(10, 0, 10, 0); l.setSpacing(10)
        self._av  = _make_avatar(avatar_b64, 40)
        self._lbl = QLabel(username); self._lbl.setStyleSheet("background:transparent;")
        l.addWidget(self._av); l.addWidget(self._lbl, stretch=1)
        self._apply()

    def set_active(self, v): self._active = v; self._apply()
    def unlock(self): self._clickable = True; self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def _apply(self):
        if self._active:
            self.setStyleSheet(f"QWidget{{background:{GOLD_GLOW};border:2px solid {GOLD};border-radius:12px;}}")
            self._lbl.setStyleSheet(f"color:{GOLD};font-size:15px;font-weight:800;background:transparent;")
        else:
            self.setStyleSheet(f"QWidget{{background:rgba(255,255,255,0.08);border:1px solid {BORDER};border-radius:12px;}}")
            self._lbl.setStyleSheet(f"color:{TEXT};font-size:15px;font-weight:700;background:transparent;")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._clickable: self.clicked.emit()


# ── Countdown label ───────────────────────────────────────────────────────────
class CountdownLabel(QLabel):
    finished = pyqtSignal()
    def __init__(self, seconds: int, parent=None):
        super().__init__(parent)
        self._remaining = seconds
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"color:{DIM};font-size:13px;font-weight:700;background:transparent;")
        self._timer = QTimer(self); self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._update()

    def start(self): self._timer.start()
    def stop(self):  self._timer.stop()

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop(); self.finished.emit()
        else: self._update()

    def _update(self): self.setText(f"Next in {self._remaining}s")


# ── Single chain message bubble ───────────────────────────────────────────────
def _make_bubble(entry: dict, scroll_w: int) -> QWidget:
    """
    Sentence → right-aligned orange bubble (75% width)
    Drawing  → left-aligned image (50% width)
    Includes circular avatar + author name above.
    """
    etype   = entry.get("type", "sentence")
    author  = entry.get("author_username", "?")
    content = entry.get("content", "")
    avatar  = entry.get("author_avatar", "")

    outer = QWidget(); outer.setStyleSheet("background:transparent;")
    outer._is_sentence = (etype == "sentence")
    outer._is_drawing  = (etype == "drawing")
    ol = QVBoxLayout(outer); ol.setContentsMargins(0,0,0,0); ol.setSpacing(4)

    # Author row: avatar + name
    auth_row = QHBoxLayout(); auth_row.setContentsMargins(0,0,0,0); auth_row.setSpacing(6)
    av = _make_avatar(avatar, 28)
    name_lbl = QLabel(author)
    name_lbl.setStyleSheet(f"color:{DIM};font-size:12px;font-weight:700;background:transparent;")

    if etype == "sentence":
        auth_row.addStretch()
        auth_row.addWidget(name_lbl)
        auth_row.addWidget(av)
    else:
        auth_row.addWidget(av)
        auth_row.addWidget(name_lbl)
        auth_row.addStretch()
    ol.addLayout(auth_row)

    if etype == "sentence":
        max_w = max(200, int(scroll_w * 0.75))
        card  = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background:{MSG_RIGHT};
                border:1px solid rgba(249,115,22,0.50);
                border-radius:14px;
            }}
        """)
        card.setMaximumWidth(max_w)
        cl  = QHBoxLayout(card); cl.setContentsMargins(14,10,14,10)
        lbl = QLabel(f'"{content}"'); lbl.setWordWrap(True)
        lbl.setMaximumWidth(max_w - 32)
        lbl.setStyleSheet(f"color:{TEXT};font-size:16px;font-weight:600;font-style:italic;background:transparent;")
        cl.addWidget(lbl)
        row = QHBoxLayout(); row.setContentsMargins(0,0,0,0)
        row.addStretch(); row.addWidget(card)
        ol.addLayout(row)

    else:  # drawing
        max_w = max(160, int(scroll_w * 0.50))
        px    = _b64_to_pixmap(content)
        card  = QWidget()
        card.setStyleSheet(f"QWidget{{background:rgba(0,0,0,0.12);border:1px solid {BORDER};border-radius:12px;}}")
        cl    = QVBoxLayout(card); cl.setContentsMargins(8,8,8,8); cl.setSpacing(6)

        img_lbl = QLabel(); img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("background:#FFFFFF;border-radius:6px;border:none;")

        outer._px = px
        if not px.isNull():
            target_w = max_w - 16
            scaled   = px.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation)
            img_lbl.setPixmap(scaled)
            img_lbl.setFixedSize(scaled.width(), scaled.height())
            card.setFixedWidth(scaled.width() + 16)
        else:
            img_lbl.setText("(no image)"); img_lbl.setFixedHeight(50)
            card.setFixedWidth(max_w)

        cl.addWidget(img_lbl, alignment=Qt.AlignmentFlag.AlignLeft)

        save_btn = QPushButton("💾  Save")
        save_btn.setFixedHeight(28); save_btn.setFixedWidth(90)
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.setStyleSheet(f"QPushButton{{background:rgba(249,115,22,0.75);border:none;border-radius:8px;color:#FFF;font-size:11px;font-weight:700;}}QPushButton:hover{{background:{ORANGE};}}")
        outer._save_btn = save_btn
        cl.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        row = QHBoxLayout(); row.setContentsMargins(0,0,0,0)
        row.addWidget(card); row.addStretch()
        ol.addLayout(row)

    return outer


# ── Results screen ────────────────────────────────────────────────────────────
class ResultsScreen(QWidget):
    back_requested     = pyqtSignal()
    host_next_requested = pyqtSignal()   # host pressed Next — tell window to broadcast

    def __init__(self, chains, is_host=False,
                 letter_secs=0.125, drawing_secs=5.0,
                 host_control=False, parent=None):
        super().__init__(parent)
        self._chains       = chains
        self._is_host      = is_host
        self._host_control = host_control
        self._letter_secs  = letter_secs
        self._drawing_secs = drawing_secs
        self.DELAY_DRAWING = max(1000, int(drawing_secs * 1000))
        self.DELAY_NEXT    = 10000

        self._current_chain = 0
        self._current_entry = -1
        self._entry_widgets = []
        self._revealing     = True
        self._done          = False
        self._countdown     = None

        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.timeout.connect(self._reveal_next)

        try:
            from app import scale as ui_scale; self._S = ui_scale.get()
        except ImportError: self._S = 1.0

        self.setStyleSheet("background:transparent;")
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        S = self._S
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        pad = QWidget(); pad.setStyleSheet("background:transparent;")
        pad_l = QVBoxLayout(pad)
        pad_l.setContentsMargins(int(24*S),int(16*S),int(24*S),int(16*S))

        card = QWidget(); card.setObjectName("RC")
        card.setStyleSheet(f"QWidget#RC{{background:{PANEL_BG};border:1px solid {BORDER};border-radius:20px;}}")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_l = QHBoxLayout(card); card_l.setContentsMargins(0,0,0,0); card_l.setSpacing(0)

        # ── Left panel ────────────────────────────────────────────────────
        left = QWidget(); left.setFixedWidth(int(220*S))
        left.setStyleSheet(f"QWidget{{background:rgba(0,0,0,0.12);border-right:1px solid {BORDER};}}")
        ll = QVBoxLayout(left); ll.setContentsMargins(int(10*S),int(16*S),int(10*S),int(16*S)); ll.setSpacing(8)

        title = QLabel("RESULTS"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{GOLD};font-size:{int(15*S)}px;font-weight:900;letter-spacing:3px;background:transparent;")
        ll.addWidget(title); ll.addWidget(_div()); ll.addSpacing(4)

        self._tabs = []
        for i, chain in enumerate(self._chains):
            name   = chain.get("owner_username", f"Player {i+1}")
            avatar = chain.get("owner_avatar", "")
            tab    = PlayerTab(name, avatar_b64=avatar, active=(i==0))
            tab.clicked.connect(lambda _, idx=i: self._free_select(idx))
            self._tabs.append(tab); ll.addWidget(tab)

        ll.addStretch()

        back = QPushButton("← Leave"); back.setFixedHeight(42)
        back.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back.clicked.connect(self.back_requested)
        back.setStyleSheet(f"QPushButton{{background:rgba(239,68,68,0.75);border:none;border-radius:12px;color:#FFF;font-size:{int(13*S)}px;font-weight:800;}}QPushButton:hover{{background:rgba(239,68,68,0.95);}}")
        ll.addWidget(back); card_l.addWidget(left)

        # ── Right scroll ──────────────────────────────────────────────────
        right = QWidget()
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right.setStyleSheet("background:transparent;")
        right_l = QVBoxLayout(right); right_l.setContentsMargins(0,0,0,0); right_l.setSpacing(0)

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

        self._inner = QWidget(); self._inner.setStyleSheet("background:transparent;")
        self._vbox  = QVBoxLayout(self._inner)
        self._vbox.setContentsMargins(int(16*S),int(16*S),int(16*S),int(24*S))
        self._vbox.setSpacing(int(10*S))
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll.setWidget(self._inner)
        right_l.addWidget(self._scroll, stretch=1)

        # ── Bottom next bar (shown after each chain finishes) ─────────────
        self._next_bar = QWidget()
        self._next_bar.setStyleSheet(f"background:rgba(0,0,0,0.22);border-top:1px solid {BORDER};")
        self._next_bar.setFixedHeight(int(80*S))
        self._next_bar.setVisible(False)
        nb_l = QVBoxLayout(self._next_bar)
        nb_l.setContentsMargins(int(24*S), int(6*S), int(24*S), int(8*S))
        nb_l.setSpacing(4)

        self._countdown_lbl = QLabel("")
        self._countdown_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_lbl.setStyleSheet(f"color:{DIM};font-size:13px;font-weight:700;background:transparent;")
        nb_l.addWidget(self._countdown_lbl)

        self._next_btn = QPushButton("Next  →")
        self._next_btn.setFixedHeight(int(36*S))
        self._next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._next_btn.clicked.connect(self._on_next_clicked)
        self._next_btn.setStyleSheet(f"""
            QPushButton{{
                background:{ORANGE};border:none;border-radius:{int(10*S)}px;
                color:#FFF;font-size:{int(15*S)}px;font-weight:800;letter-spacing:1px;
            }}
            QPushButton:hover{{background:{ORANGE_H};}}
        """)
        nb_l.addWidget(self._next_btn)
        right_l.addWidget(self._next_bar)

        card_l.addWidget(right)

        pad_l.addWidget(card); root.addWidget(pad)
        self._overlay = BlackOverlay(self)

    def resizeEvent(self, e):
        super().resizeEvent(e); self._overlay.setGeometry(self.rect())

    def mousePressEvent(self, e):
        if self._host_control and self._revealing and self._reveal_timer.isActive():
            self._reveal_timer.stop(); self._reveal_next()

    # ── Intro ─────────────────────────────────────────────────────────────────
    def start_reveal(self):
        self._overlay.setGeometry(self.rect())
        self._overlay.show(); self._overlay._fx.setOpacity(1.0)

        self._ann = QLabel("HERE ARE THE RESULTS...", self._overlay)
        self._ann.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ann.setStyleSheet("color:#FFFFFF;font-size:42px;font-weight:900;letter-spacing:4px;background:transparent;")
        self._ann.setGeometry(self._overlay.rect())
        ann_fx = QGraphicsOpacityEffect(self._ann); ann_fx.setOpacity(0.0)
        self._ann.setGraphicsEffect(ann_fx); self._ann.show()

        seq = QSequentialAnimationGroup(self); seq.addPause(400)
        a1  = QPropertyAnimation(ann_fx, b"opacity"); a1.setDuration(900)
        a1.setStartValue(0.0); a1.setEndValue(1.0); a1.setEasingCurve(QEasingCurve.Type.InOutQuad)
        seq.addAnimation(a1); seq.addPause(2000)
        par = QParallelAnimationGroup()
        a2  = QPropertyAnimation(ann_fx, b"opacity"); a2.setDuration(600)
        a2.setStartValue(1.0); a2.setEndValue(0.0); par.addAnimation(a2)
        a3  = QPropertyAnimation(self._overlay._fx, b"opacity"); a3.setDuration(1800)
        a3.setStartValue(1.0); a3.setEndValue(0.0); a3.setEasingCurve(QEasingCurve.Type.InOutQuad)
        par.addAnimation(a3); seq.addAnimation(par)
        seq.finished.connect(self._intro_done); self._intro_seq = seq; seq.start()

    def _intro_done(self):
        self._overlay.hide()
        self._overlay.setGraphicsEffect(None)   # detach effect to stop repaints
        self._ann.hide()
        self._start_chain(0)

    # ── Chain reveal ──────────────────────────────────────────────────────────
    def _scroll_width(self) -> int:
        vp = self._scroll.viewport()
        return vp.width() if vp else 500

    def _start_chain(self, idx: int):
        self._current_chain = idx; self._current_entry = -1; self._entry_widgets = []

        # Clear
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # Hide next bar
        self._next_bar.setVisible(False)
        if self._countdown:
            self._countdown.stop(); self._countdown = None

        for i, tab in enumerate(self._tabs): tab.set_active(i == idx)

        chain   = self._chains[idx] if idx < len(self._chains) else {}
        entries = chain.get("entries", [])
        owner   = chain.get("owner_username", f"Player {idx+1}")

        # Header
        hdr = QLabel(f"✦  {owner}'s Chain"); hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet(f"color:{GOLD};font-size:20px;font-weight:900;letter-spacing:2px;background:transparent;")
        hdr.hide(); self._vbox.addWidget(hdr); self._entry_widgets.append(hdr)
        dv = _div(); dv.hide(); self._vbox.addWidget(dv); self._entry_widgets.append(dv)

        sw = self._scroll_width()
        for i, entry in enumerate(entries):
            w = _make_bubble(entry, sw)
            # Wire save button if present
            if hasattr(w, '_save_btn'):
                px   = getattr(w, '_px', QPixmap())
                auth = entry.get("author_username", "?")
                w._save_btn.clicked.connect(lambda _, p=px, a=auth, b=w._save_btn: self._save(p, a, b))
            w.hide(); self._vbox.addWidget(w); self._entry_widgets.append(w)
            if i < len(entries) - 1:
                arr = QLabel("▼"); arr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arr.setStyleSheet(f"color:{GHOST};font-size:16px;background:transparent;")
                arr.hide(); self._vbox.addWidget(arr); self._entry_widgets.append(arr)

        self._reveal_next()

    def _reveal_next(self):
        self._current_entry += 1
        if self._current_entry >= len(self._entry_widgets):
            self._chain_done(); return

        w = self._entry_widgets[self._current_entry]; w.show()
        QTimer.singleShot(80, lambda: self._scroll.ensureWidgetVisible(w))

        if self._current_entry < len(self._entry_widgets) - 1:
            nw = self._entry_widgets[self._current_entry + 1]
            if getattr(nw, '_is_drawing', False):
                delay = self.DELAY_DRAWING
            elif getattr(nw, '_is_sentence', False):
                # Scale delay by actual char count
                content = ""
                # find the entry for this widget index
                entry_idx = self._bubble_index(self._current_entry + 1)
                if entry_idx is not None:
                    chain = self._chains[self._current_chain] if self._current_chain < len(self._chains) else {}
                    entries = chain.get("entries", [])
                    if entry_idx < len(entries):
                        content = entries[entry_idx].get("content", "")
                chars = max(10, len(content))
                delay = max(800, int(chars * self._letter_secs * 1000))
            else:
                delay = 500  # arrow / header
            self._reveal_timer.start(delay)

    def _bubble_index(self, widget_pos: int) -> int:
        """Map a widget list position back to the entry index in the chain."""
        # Layout: hdr(0), div(1), then for each entry: bubble, arrow (last has no arrow)
        # positions 2, 3, 4, 5 ... where even=bubble, odd=arrow
        if widget_pos < 2: return None
        pos = widget_pos - 2   # offset past header + divider
        return pos // 2        # every bubble is at even offsets

    def _chain_done(self):
        """All entries revealed — show countdown + Next button for everyone."""
        secs = self.DELAY_NEXT // 1000
        self._cnt_remaining = secs
        self._countdown_lbl.setText(f"Next in {secs}s")

        # Only show next bar if there are more chains (or we're going to all_done)
        self._next_bar.setVisible(True)

        # Guests: auto-advance. Host: also auto-advance unless host_control
        # Everyone sees the Next button, but only host can click it when host_control=True
        # Actually — Next button visible to ALL, auto-timer runs in background
        if self._countdown:
            self._countdown.stop()
        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)

        def _tick():
            self._cnt_remaining -= 1
            if self._cnt_remaining <= 0:
                self._countdown.stop()
                self._advance_chain()
            else:
                self._countdown_lbl.setText(f"Next in {self._cnt_remaining}s")

        self._countdown.timeout.connect(_tick)
        self._countdown.start()

    def _on_next_clicked(self):
        """Next button clicked — if host, broadcast to all. If guest, ignore (wait for host)."""
        if self._is_host:
            # Stop local countdown and broadcast to all clients via window
            if self._countdown:
                self._countdown.stop()
            self._next_bar.setVisible(False)
            self.host_next_requested.emit()   # window.py will call client.host_next()
            self._advance_chain()             # also advance locally
        # guests do nothing on click — they wait for HOST_NEXT broadcast

    def force_next(self):
        """Called on all clients when server broadcasts HOST_NEXT."""
        if self._countdown:
            self._countdown.stop()
        self._next_bar.setVisible(False)
        self._advance_chain()

    def _advance_chain(self):
        nxt = self._current_chain + 1
        if nxt < len(self._chains): self._start_chain(nxt)
        else: self._all_done()

    def _all_done(self):
        self._revealing = False; self._done = True
        self._next_bar.setVisible(False)
        for tab in self._tabs: tab.unlock()

    # ── Free browse ───────────────────────────────────────────────────────────
    def _free_select(self, idx: int):
        if not self._done: return
        for i, tab in enumerate(self._tabs): tab.set_active(i == idx)
        self._load_static(idx); self._scroll.verticalScrollBar().setValue(0)

    def _load_static(self, idx: int):
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        chain   = self._chains[idx] if idx < len(self._chains) else {}
        entries = chain.get("entries", [])
        owner   = chain.get("owner_username", f"Player {idx+1}")

        hdr = QLabel(f"✦  {owner}'s Chain"); hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet(f"color:{GOLD};font-size:20px;font-weight:900;letter-spacing:2px;background:transparent;")
        self._vbox.addWidget(hdr); self._vbox.addWidget(_div())

        sw = self._scroll_width()
        for i, entry in enumerate(entries):
            w = _make_bubble(entry, sw)
            if hasattr(w, '_save_btn'):
                px = getattr(w, '_px', QPixmap()); auth = entry.get("author_username","?")
                w._save_btn.clicked.connect(lambda _, p=px, a=auth, b=w._save_btn: self._save(p, a, b))
            self._vbox.addWidget(w)
            if i < len(entries)-1:
                arr = QLabel("▼"); arr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arr.setStyleSheet(f"color:{GHOST};font-size:16px;background:transparent;")
                self._vbox.addWidget(arr)

    # ── Save ──────────────────────────────────────────────────────────────────
    def _save(self, px: QPixmap, author: str, btn: QPushButton = None):
        if px.isNull(): return
        try:
            from app.screens.photos import save_drawing
            save_drawing(px, name=f"Drawing by {author}")
        except Exception as e: print(f"[Save error] {e}")
        if btn:
            orig = btn.text()
            btn.setText("✓  Saved!"); btn.setEnabled(False)
            btn.setStyleSheet(f"QPushButton{{background:rgba(34,197,94,0.85);border:none;border-radius:8px;color:#FFF;font-size:11px;font-weight:700;}}");
            QTimer.singleShot(2000, lambda: (
                btn.setText(orig), btn.setEnabled(True),
                btn.setStyleSheet(f"QPushButton{{background:rgba(249,115,22,0.75);border:none;border-radius:8px;color:#FFF;font-size:11px;font-weight:700;}}QPushButton:hover{{background:{ORANGE};}}")
            ))