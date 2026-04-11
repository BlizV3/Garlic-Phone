"""
Debug console — captures all print/stderr output and displays it
in a floating window. Toggled from the Settings panel.
"""
import sys
import io
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QCursor, QColor

TEXT   = "#00FF88"   # green terminal text
BG     = "#0D0D0D"
BORDER = "rgba(0,255,136,0.30)"


class _StreamRedirect(QObject):
    """Intercepts writes to stdout/stderr and emits them as signals."""
    written = pyqtSignal(str)

    def __init__(self, original):
        super().__init__()
        self._original = original

    def write(self, text):
        if self._original:
            self._original.write(text)
        if text.strip():
            self.written.emit(text)

    def flush(self):
        if self._original:
            self._original.flush()

    def fileno(self):
        if self._original:
            return self._original.fileno()
        return -1


class DebugConsole(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Debug Console")
        self.setMinimumSize(600, 380)
        self.resize(700, 420)
        self.setStyleSheet(f"background:{BG}; border:1px solid {BORDER}; border-radius:12px;")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # Title bar
        title_row = QHBoxLayout()
        lbl = QLabel("⬛  CONSOLE")
        lbl.setStyleSheet(f"color:{TEXT}; font-size:13px; font-weight:800; font-family:Consolas,monospace; background:transparent;")
        clear_btn = QPushButton("CLEAR")
        clear_btn.setFixedHeight(28)
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.setStyleSheet(f"QPushButton{{background:rgba(0,255,136,0.12);border:1px solid {BORDER};border-radius:6px;color:{TEXT};font-size:11px;font-weight:700;padding:0 10px;}}QPushButton:hover{{background:rgba(0,255,136,0.25);}}")
        clear_btn.clicked.connect(self._clear)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(f"QPushButton{{background:rgba(239,68,68,0.40);border:none;border-radius:6px;color:#FFF;font-size:12px;font-weight:800;}}QPushButton:hover{{background:rgba(239,68,68,0.80);}}")
        close_btn.clicked.connect(self.hide)
        title_row.addWidget(lbl, stretch=1)
        title_row.addWidget(clear_btn)
        title_row.addSpacing(4)
        title_row.addWidget(close_btn)
        root.addLayout(title_row)

        # Output area
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 11))
        self._output.setStyleSheet(f"""
            QTextEdit {{
                background:{BG}; color:{TEXT};
                border:1px solid {BORDER}; border-radius:8px;
                padding:6px;
            }}
        """)
        root.addWidget(self._output)

        # Hook stdout and stderr
        self._stdout_hook = _StreamRedirect(sys.stdout)
        self._stderr_hook = _StreamRedirect(sys.stderr)
        self._stdout_hook.written.connect(self._append)
        self._stderr_hook.written.connect(lambda t: self._append(t, error=True))
        sys.stdout = self._stdout_hook
        sys.stderr = self._stderr_hook

    def _append(self, text: str, error: bool = False):
        color = "#FF6B6B" if error else TEXT
        # Escape HTML
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._output.append(f'<span style="color:{color};white-space:pre;">{safe}</span>')
        # Auto-scroll
        sb = self._output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear(self):
        self._output.clear()

    def restore_streams(self):
        """Call on app exit to restore original streams."""
        sys.stdout = self._stdout_hook._original
        sys.stderr = self._stderr_hook._original