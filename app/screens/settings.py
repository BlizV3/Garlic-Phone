from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSlider
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QCursor

TEXT_LIGHT = "#FFFFFF"
TEXT_DIM   = "#E0F2FE"
ORANGE     = "#F97316"
BORDER     = "rgba(255,255,255,0.35)"


def _divider() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.Shape.HLine)
    d.setStyleSheet("background: rgba(255,255,255,0.2); max-height:1px; border:none;")
    return d

def _lbl(text: str, dim: bool = False) -> QLabel:
    color = TEXT_DIM if dim else TEXT_LIGHT
    fs    = "15px" if dim else "18px"
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{color}; font-size:{fs}; font-weight:700; "
        f"letter-spacing:1px; background:transparent; border:none;")
    return l


class SettingsPanel(QWidget):
    window_mode    = pyqtSignal(str)   # "windowed" | "fullscreen" | "borderless"
    test_requested = pyqtSignal()      # launch solo test session

    def __init__(self, sfx, parent=None):
        super().__init__(parent)
        self._sfx = sfx
        self._win_mode = "windowed"

        self.setFixedWidth(390)
        self.setObjectName("settingsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#settingsPanel {
                background: rgba(0,0,0,0.40);
                border: 1px solid rgba(255,255,255,0.35);
                border-radius: 20px;
            }
            QWidget#settingsPanel QLabel {
                background: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        # Title
        title = QLabel("SETTINGS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:22px; font-weight:900; "
            f"letter-spacing:4px; background:transparent; border:none;")
        layout.addWidget(title)
        layout.addWidget(_divider())

        # ── Music volume ───────────────────────────────────────────────────
        layout.addWidget(_lbl("MUSIC VOLUME"))
        self._music_slider = self._make_slider(10)
        self._music_slider.valueChanged.connect(self._on_music_vol)
        layout.addWidget(self._music_slider)
        self._music_vol_lbl = _lbl("10%", dim=True)
        self._music_vol_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._music_vol_lbl)

        layout.addWidget(_divider())

        # ── SFX volume ─────────────────────────────────────────────────────
        layout.addWidget(_lbl("SFX VOLUME"))
        self._sfx_slider = self._make_slider(10)
        self._sfx_slider.valueChanged.connect(self._on_sfx_vol)
        layout.addWidget(self._sfx_slider)
        self._sfx_vol_lbl = _lbl("10%", dim=True)
        self._sfx_vol_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._sfx_vol_lbl)

        layout.addWidget(_divider())

        # ── Window mode ────────────────────────────────────────────────────
        layout.addWidget(_lbl("WINDOW MODE"))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_btns = {}
        for mode, label in [("windowed", "WINDOW"), ("fullscreen", "FULLSCREEN"), ("borderless", "BORDERLESS")]:
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, m=mode: self._on_mode(m))
            self._mode_btns[mode] = btn
            mode_row.addWidget(btn)
        layout.addLayout(mode_row)
        self._apply_mode_styles()

        layout.addWidget(_divider())

        # ── Test mode ──────────────────────────────────────────────────────
        test_btn = QPushButton("🧪  SOLO TEST MODE")
        test_btn.setFixedHeight(46)
        test_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        test_btn.clicked.connect(self._on_test_mode)
        test_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(139,92,246,0.75);
                border: 2px solid rgba(139,92,246,0.4);
                border-radius: 14px;
                color: #FFFFFF;
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: rgba(139,92,246,0.95);
                border: 2px solid rgba(139,92,246,0.8);
            }}
        """)
        layout.addWidget(test_btn)

        # ── Debug console ──────────────────────────────────────────────────
        console_btn = QPushButton("⬛  DEBUG CONSOLE")
        console_btn.setFixedHeight(46)
        console_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        console_btn.clicked.connect(self._on_console)
        console_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(15,15,15,0.85);
                border: 2px solid rgba(0,255,136,0.35);
                border-radius: 14px;
                color: #00FF88;
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 1px;
                font-family: Consolas, monospace;
            }}
            QPushButton:hover {{
                background: rgba(0,255,136,0.12);
                border: 2px solid rgba(0,255,136,0.70);
            }}
        """)
        layout.addWidget(console_btn)
        self._console_window = None

        self.adjustSize()

        # Initial values
        self._sfx.set_music_volume(0.10)
        self._sfx.set_volume(0.1)

        if parent:
            parent.installEventFilter(self)

    # ── Close on outside click ─────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if self.isVisible() and event.type() == QEvent.Type.MouseButtonPress:
            click_pos  = event.globalPosition().toPoint()
            panel_rect = self.rect()
            panel_rect.moveTo(self.mapToGlobal(self.rect().topLeft()))
            if not panel_rect.contains(click_pos):
                self.hide()
        return False

    # ── Helpers ───────────────────────────────────────────────────────────

    def _make_slider(self, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, 100)
        s.setValue(value)
        s.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        s.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255,255,255,0.15);
                height: 8px; border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 20px; height: 20px;
                margin: -6px 0; border-radius: 10px;
            }
            QSlider::sub-page:horizontal {
                background: #F97316; border-radius: 4px;
            }
        """)
        return s

    def _apply_mode_styles(self):
        for mode, btn in self._mode_btns.items():
            active = (mode == self._win_mode)
            bg = ORANGE if active else "rgba(255,255,255,0.12)"
            border = "rgba(255,255,255,0.8)" if active else "rgba(255,255,255,0.25)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    border: 2px solid {border};
                    border-radius: 10px;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 800;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.22);
                    border: 2px solid rgba(255,255,255,0.6);
                }}
            """)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_music_vol(self, value: int):
        self._music_vol_lbl.setText(f"{value}%")
        self._sfx.set_music_volume(value / 100.0)

    def _on_sfx_vol(self, value: int):
        self._sfx_vol_lbl.setText(f"{value}%")
        self._sfx.set_volume(value / 100.0)

    def _on_test_mode(self):
        self.hide()
        self.test_requested.emit()

    def _on_console(self):
        self.hide()
        if self._console_window is None:
            from app.screens.console import DebugConsole
            self._console_window = DebugConsole()
        self._console_window.show()
        self._console_window.raise_()

    def _on_mode(self, mode: str):
        self._win_mode = mode
        self._apply_mode_styles()
        self.window_mode.emit(mode)