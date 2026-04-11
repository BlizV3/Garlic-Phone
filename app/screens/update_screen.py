"""
Update screen — shown when the app version is behind the latest GitHub release.
Downloads and installs the new .exe automatically.
"""
import os
import sys
import threading
import urllib.request
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QCursor

from app.paths import asset

TEXT    = "#FFFFFF"
DIM     = "#E0F2FE"
ORANGE  = "#F97316"
ORANGE_H = "#FB923C"
RED     = "rgba(239,68,68,0.80)"


class UpdateScreen(QWidget):
    """Shown when the installed version is behind the latest GitHub release."""
    skip_requested = pyqtSignal()   # player chose to play anyway (offline/skip)

    def __init__(self, current_version: str, latest_version: str,
                 download_url: str, parent=None):
        super().__init__(parent)
        self._current    = current_version
        self._latest     = latest_version
        self._dl_url     = download_url
        self._updating   = False
        self.setStyleSheet("background: transparent;")
        self._build()

    def _build(self):
        try:
            from app import scale as ui_scale; S = ui_scale.get()
        except ImportError: S = 1.0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Dark overlay card
        card = QWidget()
        card.setFixedWidth(int(560 * S))
        card.setStyleSheet("""
            QWidget {
                background: rgba(0,0,0,0.82);
                border: 1px solid rgba(255,255,255,0.20);
                border-radius: 24px;
            }
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(int(40*S), int(36*S), int(40*S), int(36*S))
        cl.setSpacing(int(16*S))
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet("background:transparent;border:none;")
        px = QPixmap(asset("icons", "thumbnail.png"))
        if not px.isNull():
            px = px.scaledToHeight(int(72*S), Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(px)
        cl.addWidget(logo_lbl)

        # Title
        title = QLabel("Update Required")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{TEXT};font-size:{int(26*S)}px;font-weight:900;background:transparent;border:none;")
        cl.addWidget(title)

        # Message
        msg = QLabel(
            f"Your Garlic Phone is out of date.\n\n"
            f"Installed:  {self._current}\n"
            f"Latest:       {self._latest}\n\n"
            "Please update to play on the server."
        )
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet(f"color:{DIM};font-size:{int(15*S)}px;font-weight:600;background:transparent;border:none;line-height:1.6;")
        cl.addWidget(msg)
        cl.addSpacing(int(8*S))

        # Progress bar (hidden until updating)
        self._progress = QProgressBar()
        self._progress.setFixedHeight(12)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255,255,255,0.12);
                border: none; border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background: {ORANGE};
                border-radius: 6px;
            }}
        """)
        self._progress.setVisible(False)
        cl.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(f"color:{DIM};font-size:{int(13*S)}px;background:transparent;border:none;")
        self._status_lbl.setVisible(False)
        cl.addWidget(self._status_lbl)

        # Update button
        self._update_btn = QPushButton("⬇  UPDATE NOW")
        self._update_btn.setFixedHeight(int(56*S))
        self._update_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_btn.clicked.connect(self._start_update)
        self._update_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ORANGE}; border: none;
                border-radius: {int(16*S)}px;
                color: #FFFFFF; font-size: {int(17*S)}px;
                font-weight: 800; letter-spacing: 1px;
            }}
            QPushButton:hover {{ background: {ORANGE_H}; }}
        """)
        cl.addWidget(self._update_btn)

        # Skip button (smaller)
        skip_btn = QPushButton("Skip for now (may not connect)")
        skip_btn.setFixedHeight(int(36*S))
        skip_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        skip_btn.clicked.connect(self.skip_requested)
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: rgba(255,255,255,0.40);
                font-size: {int(12*S)}px; font-weight: 600;
            }}
            QPushButton:hover {{ color: rgba(255,255,255,0.70); }}
        """)
        cl.addWidget(skip_btn)

        root.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

    # ── Update logic ──────────────────────────────────────────────────────────

    def _start_update(self):
        if self._updating:
            return
        self._updating = True
        self._update_btn.setEnabled(False)
        self._update_btn.setText("Downloading...")
        self._progress.setVisible(True)
        self._status_lbl.setVisible(True)
        self._status_lbl.setText("Starting download...")

        threading.Thread(target=self._download_and_replace, daemon=True).start()

    def _download_and_replace(self):
        try:
            import tempfile, subprocess, shutil, time

            # Determine download destination
            if getattr(sys, "frozen", False):
                # Running as .exe — replace ourselves
                current_exe = sys.executable
                dest_dir    = os.path.dirname(current_exe)
                exe_name    = os.path.basename(current_exe)
            else:
                # Dev mode — download next to main.py
                current_exe = None
                dest_dir    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                exe_name    = "Garlic Phone.exe"

            tmp_path = os.path.join(tempfile.gettempdir(), f"GarlicPhone_update_{self._latest}.exe")

            # Download with progress
            def _progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    pct = min(100, int(block_num * block_size * 100 / total_size))
                    QTimer.singleShot(0, lambda p=pct: self._set_progress(p, f"Downloading... {p}%"))

            urllib.request.urlretrieve(self._dl_url, tmp_path, _progress_hook)

            self._set_progress(100, "Download complete — installing...")

            new_exe = os.path.join(dest_dir, exe_name)

            if current_exe and os.path.exists(current_exe):
                # Write a tiny batch script that waits for this process to exit,
                # replaces the exe, then relaunches it
                bat = os.path.join(tempfile.gettempdir(), "garlic_update.bat")
                with open(bat, "w") as f:
                    f.write(f"""@echo off
timeout /t 2 /nobreak > nul
move /y "{tmp_path}" "{new_exe}"
start "" "{new_exe}"
del "%~f0"
""")
                self._set_progress(100, "Relaunching...")
                subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000)
                QTimer.singleShot(800, lambda: sys.exit(0))
            else:
                # Dev mode — just copy and inform
                shutil.copy2(tmp_path, new_exe)
                self._set_progress(100, f"Saved to {new_exe} — please restart manually")

        except Exception as e:
            self._set_progress(0, f"Update failed: {e}")
            QTimer.singleShot(0, lambda: self._update_btn.setEnabled(True))
            QTimer.singleShot(0, lambda: self._update_btn.setText("⬇  RETRY UPDATE"))

    def _set_progress(self, pct: int, text: str):
        QTimer.singleShot(0, lambda: (
            self._progress.setValue(pct),
            self._status_lbl.setText(text),
        ))