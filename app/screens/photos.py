import os
import json
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QScrollArea, QGridLayout,
    QSizePolicy, QFrame, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QCursor, QColor, QPainter, QBrush, QPen

BG         = "#0EA5E9"
CARD_BG    = "rgba(0,0,0,0.18)"
BORDER     = "rgba(255,255,255,0.40)"
BORDER_HOV = "rgba(255,255,255,0.85)"
TEXT_LIGHT = "#FFFFFF"
TEXT_DIM   = "#E0F2FE"
TEXT_GRAY  = "rgba(255,255,255,0.50)"
ORANGE     = "#F97316"
ORANGE_HOV = "#FB923C"
RED        = "rgba(239,68,68,0.80)"
RED_HOV    = "rgba(239,68,68,0.95)"

import sys

# Photos live next to the .exe when frozen, or in project root in dev
if getattr(sys, "frozen", False):
    # Bundled — store next to the .exe so photos persist between runs
    _app_dir = os.path.dirname(sys.executable)
else:
    # Development — store in project root
    _app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

PHOTOS_DIR = os.path.join(_app_dir, "photos")
META_FILE  = os.path.join(PHOTOS_DIR, "meta.json")

os.makedirs(PHOTOS_DIR, exist_ok=True)


# ── Persistence helpers ────────────────────────────────────────────────────────

def load_meta() -> list:
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_meta(entries: list):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

def folder_size_str() -> str:
    total = 0
    for fn in os.listdir(PHOTOS_DIR):
        fp = os.path.join(PHOTOS_DIR, fn)
        if os.path.isfile(fp):
            total += os.path.getsize(fp)
    if total < 1024:
        return f"{total} B"
    elif total < 1024 ** 2:
        return f"{total / 1024:.1f} KB"
    elif total < 1024 ** 3:
        return f"{total / 1024**2:.1f} MB"
    else:
        return f"{total / 1024**3:.2f} GB"

def save_drawing(pixmap: QPixmap, name: str = None) -> dict:
    """Save a QPixmap to the photos folder and return the metadata entry."""
    now = datetime.now()
    # Windows-safe date formatting — strip leading zeros manually
    hour   = now.strftime("%I").lstrip("0") or "12"
    minute = now.strftime("%M")
    ampm   = now.strftime("%p")
    month  = str(now.month)
    day    = str(now.day)
    year   = str(now.year)
    default_name = f"{hour}:{minute}{ampm} {month}/{day}/{year}"

    entry = {
        "filename": f"photo_{now.strftime('%Y%m%d_%H%M%S_%f')}.png",
        "name":     name or default_name,
        "created":  now.isoformat(),
    }
    path = os.path.join(PHOTOS_DIR, entry["filename"])
    pixmap.save(path, "PNG")
    entries = load_meta()
    entries.insert(0, entry)
    save_meta(entries)
    return entry


# ── Photo card (thumbnail in grid) ────────────────────────────────────────────

class PhotoCard(QWidget):
    clicked       = pyqtSignal(dict)   # emits the entry dict
    select_toggled = pyqtSignal(dict, bool)

    THUMB_W = 260
    THUMB_H = 180

    def __init__(self, entry: dict, select_mode: bool = False, parent=None):
        super().__init__(parent)
        self._entry       = entry
        self._select_mode = select_mode
        self._selected    = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedWidth(self.THUMB_W)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Card frame
        self._frame = QWidget()
        self._frame.setObjectName("photoCard")
        self._frame.setStyleSheet(f"""
            QWidget#photoCard {{
                background: {CARD_BG};
                border: 2px solid {BORDER};
                border-radius: 14px;
            }}
        """)
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(8, 8, 8, 10)
        frame_layout.setSpacing(6)

        # Thumbnail
        self._thumb = QLabel()
        self._thumb.setFixedSize(self.THUMB_W - 16, self.THUMB_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet("background: #FFFFFF; border-radius: 8px; border: none;")
        self._load_thumb()
        frame_layout.addWidget(self._thumb)

        # Name
        name_lbl = QLabel(self._entry.get("name", "Untitled"))
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:14px; font-weight:700; "
            f"background:transparent; border:none;")
        frame_layout.addWidget(name_lbl)

        # Date
        created = self._entry.get("created", "")
        try:
            dt = datetime.fromisoformat(created)
            date_str = dt.strftime("%I:%M %p  %m/%d/%Y").lstrip("0")
        except Exception:
            date_str = created
        date_lbl = QLabel(date_str)
        date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_lbl.setStyleSheet(
            f"color:{TEXT_GRAY}; font-size:11px; font-weight:500; "
            f"background:transparent; border:none;")
        frame_layout.addWidget(date_lbl)

        layout.addWidget(self._frame)

        # Selection checkbox overlay
        self._check = QLabel("✓")
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setFixedSize(28, 28)
        self._check.setVisible(False)
        self._check.setStyleSheet("""
            background: #F97316;
            border-radius: 14px;
            color: white;
            font-size: 14px;
            font-weight: 900;
        """)

    def _load_thumb(self):
        path = os.path.join(PHOTOS_DIR, self._entry.get("filename", ""))
        if os.path.exists(path):
            px = QPixmap(path).scaled(
                self.THUMB_W - 16, self.THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._thumb.setPixmap(px)
        else:
            self._thumb.setText("Missing")

    def set_select_mode(self, on: bool):
        self._select_mode = on
        if not on:
            self._selected = False
        self._update_style()

    def _update_style(self):
        if self._selected:
            self._frame.setStyleSheet(f"""
                QWidget#photoCard {{
                    background: rgba(249,115,22,0.25);
                    border: 2px solid {ORANGE};
                    border-radius: 14px;
                }}
            """)
        else:
            self._frame.setStyleSheet(f"""
                QWidget#photoCard {{
                    background: {CARD_BG};
                    border: 2px solid {BORDER};
                    border-radius: 14px;
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._select_mode:
            self._selected = not self._selected
            self._update_style()
            self.select_toggled.emit(self._entry, self._selected)
        else:
            self.clicked.emit(self._entry)

    def is_selected(self) -> bool:
        return self._selected

    def entry(self) -> dict:
        return self._entry


# ── Photo viewer (fullscreen single photo) ─────────────────────────────────────

class PhotoViewer(QWidget):
    closed = pyqtSignal()

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self._entry = entry
        self.setStyleSheet("background: transparent;")
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 30, 40, 30)
        outer.setSpacing(0)

        # ── Big card frame ────────────────────────────────────────────────
        card = QWidget()
        card.setObjectName("viewerCard")
        card.setStyleSheet(f"""
            QWidget#viewerCard {{
                background: rgba(0,0,0,0.18);
                border: 2px solid rgba(255,255,255,0.40);
                border-radius: 20px;
            }}
            QWidget#viewerCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        # Image — fills most of the card
        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet(
            "background: #FFFFFF; border-radius: 12px; border: none;")
        img_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        path = os.path.join(PHOTOS_DIR, self._entry.get("filename", ""))
        if os.path.exists(path):
            px = QPixmap(path)
            img_lbl.setPixmap(px.scaled(
                860, 560,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            img_lbl.setText("Image not found")
        card_layout.addWidget(img_lbl, stretch=1)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background: rgba(255,255,255,0.20); max-height:1px; border:none;")
        card_layout.addWidget(div)

        # Bottom row — back | name+date (centre) | download
        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        bottom.setContentsMargins(0, 0, 0, 0)

        close_btn = QPushButton("← BACK")
        close_btn.setFixedHeight(52)
        close_btn.setMinimumWidth(140)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.closed)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {RED};
                border: none;
                border-radius: 26px;
                color: {TEXT_LIGHT};
                font-size: 16px;
                font-weight: 800;
                letter-spacing: 2px;
                padding: 0 28px;
            }}
            QPushButton:hover {{ background: {RED_HOV}; }}
        """)

        # Centre — name + date stacked
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name_lbl = QLabel(self._entry.get("name", "Untitled"))
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:16px; font-weight:800; letter-spacing:1px;")
        info_col.addWidget(name_lbl)

        created = self._entry.get("created", "")
        try:
            dt = datetime.fromisoformat(created)
            date_str = f"{dt.strftime('%I').lstrip('0') or '12'}:{dt.strftime('%M %p')}  {dt.month}/{dt.day}/{dt.year}"
        except Exception:
            date_str = created
        date_lbl = QLabel(date_str)
        date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_lbl.setStyleSheet(
            f"color:{TEXT_GRAY}; font-size:12px; font-weight:500; letter-spacing:1px;")
        info_col.addWidget(date_lbl)

        info_w = QWidget()
        info_w.setStyleSheet("background:transparent; border:none;")
        info_w.setLayout(info_col)

        download_btn = QPushButton("⬇  DOWNLOAD")
        download_btn.setFixedHeight(52)
        download_btn.setMinimumWidth(180)
        download_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        download_btn.clicked.connect(self._download)
        download_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ORANGE};
                border: none;
                border-radius: 26px;
                color: {TEXT_LIGHT};
                font-size: 16px;
                font-weight: 800;
                letter-spacing: 2px;
                padding: 0 28px;
            }}
            QPushButton:hover {{ background: {ORANGE_HOV}; }}
        """)

        bottom.addWidget(close_btn)
        bottom.addWidget(info_w, stretch=1)
        bottom.addWidget(download_btn)
        card_layout.addLayout(bottom)

        outer.addWidget(card)

    def _download(self):
        path = os.path.join(PHOTOS_DIR, self._entry.get("filename", ""))
        default = os.path.join(os.path.expanduser("~"), "Downloads",
                               self._entry.get("filename", "drawing.png"))
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Drawing", default, "PNG Images (*.png)"
        )
        if dest:
            shutil.copy2(path, dest)


# ── Photos page ────────────────────────────────────────────────────────────────

class PhotosScreen(QWidget):
    back_requested = pyqtSignal()

    COLS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._select_mode = False
        self._selected    = set()   # filenames
        self._viewer      = None
        self._build()
        self._refresh()

    def _build(self):
        # Outer padded wrapper (same pattern as create/join screens)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._pad = QWidget()
        self._pad.setStyleSheet("background: transparent;")
        self._pad_layout = QVBoxLayout(self._pad)
        self._pad_layout.setContentsMargins(60, 40, 60, 40)

        # ── Card ──────────────────────────────────────────────────────────
        card = QWidget()
        card.setObjectName("photosCard")
        card.setStyleSheet(f"""
            QWidget#photosCard {{
                background: {CARD_BG};
                border: 2px solid {BORDER};
                border-radius: 28px;
            }}
            QWidget#photosCard QLabel {{
                background: transparent;
                border: none;
                border-radius: 0px;
            }}
            QWidget#photosCard QWidget {{
                background: transparent;
                border: none;
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(card)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(14)

        # Title
        title = QLabel("MY PHOTOS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:38px; font-weight:900; letter-spacing:4px;")
        root.addWidget(title)
        div0 = QFrame(); div0.setFrameShape(QFrame.Shape.HLine)
        div0.setStyleSheet("background: rgba(255,255,255,0.15); max-height:1px; border:none;")
        root.addWidget(div0)

        # ── Top bar ────────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(14)
        top.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._back_btn = QPushButton("← LEAVE")
        self._back_btn.setFixedSize(160, 46)
        self._back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._back_btn.clicked.connect(self.back_requested)
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {RED};
                border: none;
                border-radius: 23px;
                color: {TEXT_LIGHT};
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 2px;
                padding: 0 20px;
            }}
            QPushButton:hover {{ background: {RED_HOV}; }}
        """)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search photos…")
        self._search.setFixedHeight(46)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(0,0,0,0.20);
                border: 2px solid {BORDER};
                border-radius: 23px;
                color: {TEXT_LIGHT};
                font-size: 15px;
                font-weight: 600;
                padding: 0 20px;
                letter-spacing: 1px;
            }}
            QLineEdit:focus {{ border: 2px solid {BORDER_HOV}; }}
        """)
        self._search.textChanged.connect(self._refresh)

        self._trash_btn = QPushButton("🗑  SELECT")
        self._trash_btn.setFixedSize(160, 46)
        self._trash_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._trash_btn.clicked.connect(self._toggle_select_mode)
        self._trash_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,68,68,0.70);
                border: none;
                border-radius: 23px;
                color: {TEXT_LIGHT};
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 1px;
                padding: 0 20px;
            }}
            QPushButton:hover {{ background: {RED_HOV}; }}
        """)

        top.addWidget(self._back_btn)
        top.addWidget(self._search, stretch=1)
        top.addWidget(self._trash_btn)
        root.addLayout(top)

        # Storage label sits directly below the leave button
        self._storage_lbl = QLabel("")
        self._storage_lbl.setFixedWidth(160)
        self._storage_lbl.setStyleSheet(
            f"color:{TEXT_GRAY}; font-size:12px; font-weight:600; "
            f"background:transparent; border:none;")
        self._storage_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._storage_lbl, alignment=Qt.AlignmentFlag.AlignLeft)

        # Delete confirmation bar
        self._del_bar = QWidget()
        self._del_bar.setStyleSheet("background:transparent;")
        del_layout = QHBoxLayout(self._del_bar)
        del_layout.setContentsMargins(0, 0, 0, 0)
        del_layout.setSpacing(12)
        self._del_lbl = QLabel("0 selected")
        self._del_lbl.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:15px; font-weight:700; background:transparent;")
        del_confirm = QPushButton("DELETE SELECTED")
        del_confirm.setFixedHeight(40)
        del_confirm.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_confirm.clicked.connect(self._delete_selected)
        del_confirm.setStyleSheet(f"""
            QPushButton {{
                background: {RED}; border: none; border-radius: 20px;
                color: white; font-size: 14px; font-weight: 800;
                letter-spacing: 1px; padding: 0 20px;
            }}
            QPushButton:hover {{ background: {RED_HOV}; }}
        """)
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.clicked.connect(self._toggle_select_mode)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.15); border: none;
                border-radius: 20px; color: white; font-size: 14px;
                font-weight: 800; letter-spacing: 1px; padding: 0 20px;
            }
        """)
        del_layout.addWidget(self._del_lbl)
        del_layout.addStretch()
        del_layout.addWidget(cancel_btn)
        del_layout.addWidget(del_confirm)
        self._del_bar.setVisible(False)
        root.addWidget(self._del_bar)

        # Divider
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background: rgba(255,255,255,0.20); max-height:1px; border:none;")
        root.addWidget(div)

        # Scroll area + grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(0,0,0,0.15); width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.35); border-radius: 4px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(16)
        self._grid.setContentsMargins(0, 8, 0, 8)
        self._scroll.setWidget(self._grid_widget)
        root.addWidget(self._scroll, stretch=1)

        # Empty state
        self._empty_lbl = QLabel("No photos yet — go draw something!")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:20px; font-weight:600; background:transparent;")
        self._empty_lbl.setVisible(False)
        root.addWidget(self._empty_lbl)

        self._pad_layout.addWidget(card)
        outer.addWidget(self._pad)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from app import scale as ui_scale
        S = ui_scale.get()
        pad_h = max(int(40*S), int(self.width()  * 0.07))
        pad_v = max(int(30*S), int(self.height() * 0.05))
        self._pad_layout.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        if hasattr(self, "_current_viewer") and self._current_viewer:
            self._current_viewer.setGeometry(self.rect())

    def _refresh(self):
        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query   = self._search.text().strip().lower()
        entries = load_meta()
        if query:
            entries = [e for e in entries
                       if query in e.get("name", "").lower()
                       or query in e.get("created", "").lower()]

        self._empty_lbl.setVisible(len(entries) == 0)
        self._scroll.setVisible(len(entries) > 0)
        self._storage_lbl.setText(folder_size_str())

        for i, entry in enumerate(entries):
            card = PhotoCard(entry, select_mode=self._select_mode)
            card.clicked.connect(self._open_viewer)
            card.select_toggled.connect(self._on_select_toggle)
            row, col = divmod(i, self.COLS)
            self._grid.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop)

        # Fill remaining columns with spacers
        count = len(entries)
        if count % self.COLS:
            for col in range(count % self.COLS, self.COLS):
                spacer = QWidget()
                spacer.setFixedWidth(PhotoCard.THUMB_W)
                spacer.setStyleSheet("background:transparent;")
                row = count // self.COLS
                self._grid.addWidget(spacer, row, col)

    def _toggle_select_mode(self):
        self._select_mode = not self._select_mode
        self._selected.clear()
        self._del_bar.setVisible(self._select_mode)
        self._del_lbl.setText("0 selected")
        if self._select_mode:
            self._trash_btn.setText("✕  CANCEL")
        else:
            self._trash_btn.setText("🗑  SELECT")
        self._refresh()

    def _on_select_toggle(self, entry: dict, selected: bool):
        fn = entry.get("filename", "")
        if selected:
            self._selected.add(fn)
        else:
            self._selected.discard(fn)
        n = len(self._selected)
        self._del_lbl.setText(f"{n} selected")

    def _delete_selected(self):
        if not self._selected:
            return
        entries = load_meta()
        for fn in self._selected:
            path = os.path.join(PHOTOS_DIR, fn)
            if os.path.exists(path):
                os.remove(path)
        entries = [e for e in entries if e.get("filename") not in self._selected]
        save_meta(entries)
        self._selected.clear()
        self._select_mode = False
        self._del_bar.setVisible(False)
        self._trash_btn.setText("🗑  SELECT")
        self._refresh()

    def _open_viewer(self, entry: dict):
        # Swap to viewer
        viewer = PhotoViewer(entry, parent=self)
        viewer.setGeometry(self.rect())
        viewer.closed.connect(self._close_viewer)
        viewer.show()
        viewer.raise_()
        self._current_viewer = viewer

    def _close_viewer(self):
        if hasattr(self, "_current_viewer") and self._current_viewer:
            self._current_viewer.hide()
            self._current_viewer.deleteLater()
            self._current_viewer = None