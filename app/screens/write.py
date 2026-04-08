import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QBrush, QCursor, QFont

BG         = "#0EA5E9"
BORDER     = "rgba(255,255,255,0.45)"
BORDER_HOV = "rgba(255,255,255,0.90)"
TEXT_LIGHT = "#FFFFFF"
TEXT_DIM   = "#E0F2FE"
ORANGE     = "#F97316"
ORANGE_HOV = "#FB923C"

from app.paths import asset as _asset_fn

def _load(name: str, size: int) -> QPixmap:
    path = _asset_fn("icons", name)
    px   = QPixmap(path)
    if px.isNull():
        return QPixmap()
    return px.scaled(size, size,
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)


# ── Timer ring ─────────────────────────────────────────────────────────────────
class TimerRing(QWidget):
    def __init__(self, seconds: int = 60, panic_secs: int = 15,
                 panic_mode: bool = True, parent=None):
        super().__init__(parent)
        self._total      = seconds
        self._remaining  = seconds
        self._panic_secs = panic_secs
        self._panic_mode = panic_mode
        self._in_panic   = False
        self._timer      = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self): self._timer.start()
    def stop(self):
        self._timer.stop()
        self._stop_panic()

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
            if (self._panic_mode and not self._in_panic
                    and self._total > 0
                    and self._remaining <= self._panic_secs):
                self._start_panic()
            self.update()
        else:
            self._timer.stop()
            self._stop_panic()

    def _start_panic(self):
        self._in_panic = True
        try:
            import pygame.mixer as mx
            path = _asset_fn("music", "clock_ticking.mp3")
            mx.music.load(path)
            mx.music.play(-1)
        except Exception:
            pass

    def _stop_panic(self):
        if self._in_panic:
            self._in_panic = False
            try:
                import pygame.mixer as mx
                mx.music.stop()
            except Exception:
                pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m    = 4
        rect = QRect(m, m, self.width()-m*2, self.height()-m*2)
        p.setPen(QPen(QColor(255,255,255,60), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
        ratio = self._remaining / self._total if self._total > 0 else 0
        if self._in_panic:
            color = QColor("#EF4444")
        elif ratio <= 0.3:
            color = QColor("#F97316")
        else:
            color = QColor("#A3E635")
        p.setPen(QPen(color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 90*16, -int(ratio*360*16))
        p.setPen(color if self._in_panic else QColor(TEXT_LIGHT))
        f = QFont(); f.setPointSize(max(8, self.width()//5)); f.setBold(True); p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._remaining))



# ── Write / Guess screen ───────────────────────────────────────────────────────
class WriteScreen(QWidget):
    """
    Write mode  (image=None)    — player writes a sentence from scratch.
    Guess mode  (image=QPixmap) — player sees a drawing and guesses what it is.
    """
    submitted      = pyqtSignal(str)
    edit_requested = pyqtSignal()

    def __init__(self, round_str: str = "1/1", seconds: int = 60,
                 image: QPixmap = None, panic_mode: bool = True,
                 panic_secs: int = 15, submit_once: bool = False, parent=None):
        super().__init__(parent)
        self._round_str   = round_str
        self._seconds     = seconds
        self._image       = image
        self._mode        = "guess" if (image and not image.isNull()) else "write"
        self._panic_mode  = panic_mode
        self._panic_secs  = panic_secs
        self._submit_once = submit_once
        self._submitted   = False
        self.setStyleSheet("background: transparent;")
        self._build_ui()

    def start_timer(self):
        self._timer_ring.start()

    def _build_ui(self):
        try:
            from app import scale as ui_scale
            S = ui_scale.get()
        except ImportError:
            S = 1.0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar: round | logo | timer ──────────────────────────────────
        top = QWidget()
        top.setFixedHeight(int(72 * S))
        top.setStyleSheet("background: rgba(0,0,0,0.20); border: none;")
        top_l = QHBoxLayout(top)
        top_l.setContentsMargins(int(24*S), 0, int(24*S), 0)
        top_l.setSpacing(0)

        round_lbl = QLabel(self._round_str)
        round_lbl.setFixedWidth(int(80 * S))
        round_lbl.setStyleSheet(f"""
            color: {TEXT_LIGHT};
            font-size: {int(22*S)}px;
            font-weight: 900;
            background: transparent;
        """)

        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet("background: transparent;")
        logo_h = int(56 * S)   # constrain to bar height minus padding
        logo_px = _load("thumbnail.png", logo_h)
        if not logo_px.isNull():
            logo_lbl.setPixmap(logo_px)

        ring_sz = int(56 * S)
        self._timer_ring = TimerRing(
            self._seconds,
            panic_secs=self._panic_secs,
            panic_mode=self._panic_mode,
        )
        self._timer_ring.setFixedSize(ring_sz, ring_sz)

        # Submission count — sits left of the timer ring
        self._submit_lbl = QLabel("")
        self._submit_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._submit_lbl.setStyleSheet(f"""
            color: #FFFFFF;
            font-size: {int(20*S)}px;
            font-weight: 900;
            background: transparent;
        """)
        self._submit_lbl.setVisible(False)

        top_l.addWidget(round_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_l.addWidget(logo_lbl, stretch=1)
        top_l.addWidget(self._submit_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_l.addSpacing(int(8*S))
        top_l.addWidget(self._timer_ring, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(top)

        # ── Body ───────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(0)

        if self._mode == "guess":
            # Image fills body edge-to-edge with small padding
            img_container = QWidget()
            img_container.setStyleSheet("background: transparent;")
            img_container.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            ic_l = QVBoxLayout(img_container)
            ic_l.setContentsMargins(int(24*S), int(16*S), int(24*S), int(16*S))

            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setStyleSheet(
                "background: #FFFFFF; border-radius: 16px;"
                "border: 2px solid rgba(255,255,255,0.5);")
            img_lbl.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            scaled = self._image.scaled(
                1100, 600,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            img_lbl.setPixmap(scaled)
            ic_l.addWidget(img_lbl)
            body_l.addWidget(img_container, stretch=1)

        else:
            # Write mode — emoji + prompt, vertically centred
            body_l.addStretch(1)

            char_lbl = QLabel()
            char_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            char_lbl.setStyleSheet("background: transparent;")
            writing_px = _load("writing.png", int(540 * S))
            if not writing_px.isNull():
                char_lbl.setPixmap(writing_px)
            body_l.addWidget(char_lbl)

            body_l.addSpacing(int(24*S))

            prompt_lbl = QLabel("Write a sentence for the\nnext person to draw!")
            prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            prompt_lbl.setWordWrap(True)
            prompt_lbl.setStyleSheet(f"""
                color: {TEXT_LIGHT};
                font-size: {int(44*S)}px;
                font-weight: 900;
                letter-spacing: 1px;
                background: transparent;
            """)
            body_l.addWidget(prompt_lbl)

            body_l.addStretch(2)
            body_l.addSpacing(int(20*S))

        root.addWidget(body, stretch=1)

        # ── Bottom bar: input + done centred in screen ─────────────────────
        bottom = QWidget()
        bottom.setFixedHeight(int(120 * S))
        bottom.setStyleSheet("background: rgba(0,0,0,0.20); border: none;")
        bot_l = QVBoxLayout(bottom)
        bot_l.setContentsMargins(int(80*S), int(12*S), int(80*S), int(12*S))
        bot_l.setSpacing(int(10*S))

        self._input_style = f"""
            QLineEdit {{
                background: rgba(255,255,255,0.18);
                border: 2px solid {BORDER};
                border-radius: {int(22*S)}px;
                color: {TEXT_LIGHT};
                font-size: {int(18*S)}px;
                font-weight: 600;
                padding: 0 {int(20*S)}px;
                letter-spacing: 1px;
            }}
            QLineEdit:focus {{
                border: 2px solid {BORDER_HOV};
                background: rgba(255,255,255,0.24);
            }}
        """
        self._input_style_dim = f"""
            QLineEdit {{
                background: rgba(0,0,0,0.35);
                border: 2px solid rgba(255,255,255,0.20);
                border-radius: {int(22*S)}px;
                color: rgba(255,255,255,0.45);
                font-size: {int(18*S)}px;
                font-weight: 600;
                padding: 0 {int(20*S)}px;
                letter-spacing: 1px;
            }}
        """
        self._input = QLineEdit()
        self._input.setPlaceholderText(
            "Describe the drawing…" if self._mode == "guess"
            else "Type your sentence here…"
        )
        self._input.setFixedHeight(int(44*S))
        self._input.setStyleSheet(self._input_style)
        self._input.returnPressed.connect(self._submit)

        done_btn = QPushButton("✓  DONE")
        done_btn.setFixedHeight(int(44*S))
        done_btn.setFixedWidth(int(200*S))
        done_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        done_btn.clicked.connect(self._submit)
        done_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ORANGE};
                border: 3px solid rgba(249,115,22,0.4);
                border-radius: {int(22*S)}px;
                color: #FFFFFF;
                font-size: {int(16*S)}px;
                font-weight: 800;
                letter-spacing: 2px;
                padding: 0 {int(24*S)}px;
            }}
            QPushButton:hover {{ background: {ORANGE_HOV}; }}
        """)

        bot_l.addWidget(self._input)

        # Done row — button centred
        done_row = QHBoxLayout()
        done_row.setContentsMargins(0, 0, 0, 0)
        done_row.setSpacing(int(12*S))
        done_row.addStretch()
        self._done_btn = done_btn
        done_row.addWidget(done_btn)
        done_row.addStretch()
        bot_l.addLayout(done_row)
        root.addWidget(bottom)

    def set_submission_count(self, submitted: int, total: int):
        if hasattr(self, "_submit_lbl"):
            self._submit_lbl.setText(f"{submitted} / {total}")
            self._submit_lbl.setVisible(True)

    def _apply_done_style(self, submitted: bool):
        S = 1.0
        try:
            from app import scale as ui_scale
            S = ui_scale.get()
        except ImportError:
            pass
        if submitted:
            self._done_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.18);
                    border: 2px solid rgba(255,255,255,0.45);
                    border-radius: {int(22*S)}px;
                    color: #FFFFFF;
                    font-size: {int(16*S)}px;
                    font-weight: 800;
                    letter-spacing: 2px;
                    padding: 0 {int(24*S)}px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.28);
                    border: 2px solid rgba(255,255,255,0.80);
                }}
            """)
        else:
            self._done_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ORANGE};
                    border: 3px solid rgba(249,115,22,0.4);
                    border-radius: {int(22*S)}px;
                    color: #FFFFFF;
                    font-size: {int(16*S)}px;
                    font-weight: 800;
                    letter-spacing: 2px;
                    padding: 0 {int(24*S)}px;
                }}
                QPushButton:hover {{ background: {ORANGE_HOV}; }}
            """)

    def _submit(self):
        if getattr(self, "_submitted", False):
            # Edit mode — only allowed if submit_once is off
            if self._submit_once:
                return
            self._submitted = False
            self._done_btn.setText("✓  DONE")
            self._apply_done_style(submitted=False)
            self._input.setEnabled(True)
            self._input.setStyleSheet(self._input_style)
            self.edit_requested.emit()
        else:
            text = self._input.text().strip()
            if not text:
                self._input.setFocus()
                return
            # Lock
            self._submitted = True
            self._done_btn.setText("✏  EDIT")
            self._apply_done_style(submitted=True)
            self._input.setEnabled(False)
            self._input.setStyleSheet(self._input_style_dim)
            self.submitted.emit(text)


# ── Standalone runner ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    try:
        from app import scale as ui_scale
    except ImportError:
        class ui_scale:
            @staticmethod
            def get(): return 1.0

    class _BG(QWidget):
        def __init__(self):
            super().__init__()
            path = _asset_fn("background", "default.png")
            self._px = QPixmap(path)

        def paintEvent(self, event):
            p = QPainter(self)
            if self._px.isNull():
                p.fillRect(self.rect(), QColor(BG))
                return
            sw, sh = self.width(), self.height()
            iw, ih = self._px.width(), self._px.height()
            sc     = max(sw/iw, sh/ih)
            dw, dh = int(iw*sc), int(ih*sc)
            p.drawPixmap((sw-dw)//2, (sh-dh)//2,
                self._px.scaled(dw, dh,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))

    w  = QMainWindow()
    w.setMinimumSize(1282, 890)
    w.resize(1282, 890)
    bg = _BG()
    w.setCentralWidget(bg)
    layout = QVBoxLayout(bg)
    layout.setContentsMargins(0, 0, 0, 0)

    # Toggle MODE to test both screens
    MODE = "write"   # "write" or "guess"

    if MODE == "guess":
        test_img = QPixmap(800, 500)
        test_img.fill(QColor("#DDDDDD"))
        screen = WriteScreen(round_str="2/3", seconds=60, image=test_img)
    else:
        screen = WriteScreen(round_str="1/3", seconds=60, image=None)

    layout.addWidget(screen)
    screen.submitted.connect(lambda t: print(f"Submitted: '{t}'"))
    screen.start_timer()
    w.show()
    sys.exit(app.exec())