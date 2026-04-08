import sys
import os
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QSizePolicy,
    QFrame, QButtonGroup, QLineEdit
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPoint, QRect, QTimer, QSize, QPointF
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QPixmap, QBrush,
    QCursor, QFont, QPainterPath, QConicalGradient,
    QRadialGradient, QLinearGradient, QImage, QIcon
)

BG          = "#0EA5E9"
PANEL_BG    = "rgba(0,0,0,0.18)"
BORDER      = "rgba(255,255,255,0.35)"
BORDER_HOV  = "rgba(255,255,255,0.85)"
TEXT_LIGHT  = "#FFFFFF"
TEXT_DIM    = "#E0F2FE"
ORANGE      = "#F97316"
ORANGE_HOV  = "#FB923C"
TOOL_BG     = "rgba(255,255,255,0.12)"
TOOL_ACTIVE = "rgba(255,255,255,0.35)"

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "assets"
)

def load_icon(name: str, size: int = 28) -> QPixmap:
    path = os.path.join(ASSETS_DIR, "icons", name)
    px   = QPixmap(path)
    if px.isNull():
        return QPixmap()
    return px.scaled(size, size,
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)

def make_cursor(name: str, size: int = 32, hot_x: int = 0, hot_y: int = 0) -> QCursor:
    px = load_icon(name, size)
    if px.isNull():
        return QCursor(Qt.CursorShape.CrossCursor)
    return QCursor(px, hot_x, hot_y)

PALETTE = [
    "#FF0000", "#8B0000",  # red / dark red
    "#FF7700", "#CC5500",  # orange / dark orange
    "#FFFF00", "#CCAA00",  # yellow / dark yellow
    "#00CC00", "#006600",  # green / dark green
    "#00FFFF", "#008888",  # cyan / dark cyan
    "#0066FF", "#003399",  # blue / dark blue
    "#8800FF", "#550099",  # purple / dark purple
    "#FF00FF", "#990099",  # pink / dark pink
    "#FFFFFF", "#000000",  # white / black
]

BRUSH_SIZES = [3, 6, 10, 16, 24]


# ── Gradient slider ────────────────────────────────────────────────────────────
class GradientSlider(QWidget):
    value_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._value    = 0.0
        self._colors   = []
        self._dragging = False

    def set_stops(self, colors: list):
        self._colors = colors
        self.update()

    def set_value(self, v: float):
        self._value = max(0.0, min(1.0, v))
        self.update()

    def value(self) -> float:
        return self._value

    def _value_at(self, x: int) -> float:
        r = self._track_rect()
        return max(0.0, min(1.0, (x - r.x()) / r.width()))

    def _track_rect(self) -> QRect:
        m = 10
        return QRect(m, 6, self.width() - m * 2, self.height() - 12)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._value = self._value_at(event.position().toPoint().x())
            self.update()
            self.value_changed.emit(self._value)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._value = self._value_at(event.position().toPoint().x())
            self.update()
            self.value_changed.emit(self._value)

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._track_rect()
        if len(self._colors) >= 2:
            grad = QLinearGradient(r.left(), 0, r.right(), 0)
            step = 1.0 / (len(self._colors) - 1)
            for i, c in enumerate(self._colors):
                grad.setColorAt(i * step, c)
            p.setBrush(QBrush(grad))
        else:
            p.setBrush(QBrush(QColor("#888888")))
        p.setPen(QPen(QColor(0, 0, 0, 60), 1))
        p.drawRoundedRect(r, 6, 6)
        hx = int(r.x() + self._value * r.width())
        hy = self.height() // 2
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.setPen(QPen(QColor(0, 0, 0, 120), 2))
        p.drawEllipse(QPoint(hx, hy), 10, 10)


# ── Colour picker popup ────────────────────────────────────────────────────────
class ColourPickerPopup(QWidget):
    colour_selected = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFixedWidth(240)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget {{
                background: #1E3A5F;
                border: 2px solid {BORDER_HOV};
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {TEXT_LIGHT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
        """)

        self._hue   = 0.0
        self._light = 0.0
        self._dark  = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._preview = QWidget()
        self._preview.setFixedHeight(40)
        self._preview.setStyleSheet(
            "background: #FF0000; border-radius: 8px; border: 2px solid rgba(255,255,255,0.4);")
        layout.addWidget(self._preview)

        layout.addWidget(self._lbl("HUE"))
        self._hue_slider = GradientSlider()
        self._hue_slider.set_stops([
            QColor("#FF0000"), QColor("#FF7700"), QColor("#FFFF00"),
            QColor("#00FF00"), QColor("#00FFFF"), QColor("#0000FF"),
            QColor("#8B00FF"), QColor("#FF00FF"), QColor("#FF0000"),
        ])
        self._hue_slider.value_changed.connect(self._on_hue)
        layout.addWidget(self._hue_slider)

        layout.addWidget(self._lbl("LIGHTNESS"))
        self._light_slider = GradientSlider()
        self._light_slider.value_changed.connect(self._on_light)
        layout.addWidget(self._light_slider)

        layout.addWidget(self._lbl("DARKNESS"))
        self._dark_slider = GradientSlider()
        self._dark_slider.value_changed.connect(self._on_dark)
        layout.addWidget(self._dark_slider)

        hex_row = QHBoxLayout()
        hex_lbl = QLabel("#")
        hex_lbl.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-weight:800; font-size:14px; background:transparent; border:none;")
        self._hex_input = QLineEdit()
        self._hex_input.setMaxLength(6)
        self._hex_input.setPlaceholderText("FF0000")
        self._hex_input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.1);
                border: 2px solid {BORDER};
                border-radius: 8px;
                color: {TEXT_LIGHT};
                font-size: 13px;
                font-weight: 700;
                padding: 4px 10px;
                letter-spacing: 2px;
            }}
            QLineEdit:focus {{ border: 2px solid {BORDER_HOV}; }}
        """)
        self._hex_input.textChanged.connect(self._on_hex)
        hex_row.addWidget(hex_lbl)
        hex_row.addWidget(self._hex_input)
        layout.addLayout(hex_row)

        apply_btn = QPushButton("APPLY")
        apply_btn.setFixedHeight(36)
        apply_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ORANGE};
                border: none;
                border-radius: 10px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 800;
                letter-spacing: 2px;
            }}
            QPushButton:hover {{ background: {ORANGE_HOV}; }}
        """)
        apply_btn.clicked.connect(self._apply)
        layout.addWidget(apply_btn)

        self._refresh_all()
        self.adjustSize()

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:10px; font-weight:700; letter-spacing:1px; background:transparent; border:none;")
        return l

    def _base_color(self) -> QColor:
        return QColor.fromHsvF(self._hue, 1.0, 1.0)

    def _current_color(self) -> QColor:
        base = self._base_color()
        r = int(base.red()   + (255 - base.red())   * self._light)
        g = int(base.green() + (255 - base.green()) * self._light)
        b = int(base.blue()  + (255 - base.blue())  * self._light)
        r = int(r * (1.0 - self._dark))
        g = int(g * (1.0 - self._dark))
        b = int(b * (1.0 - self._dark))
        return QColor(r, g, b)

    def _refresh_all(self):
        c    = self._current_color()
        base = self._base_color()
        self._preview.setStyleSheet(
            f"background: {c.name()}; border-radius: 8px; border: 2px solid rgba(255,255,255,0.4);")
        self._light_slider.set_stops([base, QColor("#FFFFFF")])
        mid = QColor(
            int(base.red()   + (255 - base.red())   * self._light),
            int(base.green() + (255 - base.green()) * self._light),
            int(base.blue()  + (255 - base.blue())  * self._light),
        )
        self._dark_slider.set_stops([mid, QColor("#000000")])
        self._hex_input.blockSignals(True)
        self._hex_input.setText(c.name().lstrip("#").upper())
        self._hex_input.blockSignals(False)
        self.colour_selected.emit(c)

    def _on_hue(self, v: float):
        self._hue = v
        self._refresh_all()

    def _on_light(self, v: float):
        self._light = v
        self._refresh_all()

    def _on_dark(self, v: float):
        self._dark = v
        self._refresh_all()

    def _on_hex(self, text: str):
        text = text.strip().lstrip("#")
        if len(text) == 6:
            c = QColor(f"#{text}")
            if c.isValid():
                h, s, v, _ = c.getHsvF()
                self._hue = max(h, 0.0)
                self._hue_slider.set_value(self._hue)
                self._refresh_all()

    def _apply(self):
        self.colour_selected.emit(self._current_color())
        self.close()

    def set_color(self, color: QColor):
        h, s, v, _ = color.getHsvF()
        self._hue   = max(h, 0.0)
        self._light = max(0.0, 1.0 - s) * v
        self._dark  = max(0.0, 1.0 - v)
        self._hue_slider.set_value(self._hue)
        self._light_slider.set_value(self._light)
        self._dark_slider.set_value(self._dark)
        self._refresh_all()


# ── Canvas ─────────────────────────────────────────────────────────────────────
class DrawingCanvas(QWidget):
    colour_picked = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #FFFFFF; border-radius: 8px;")
        self._color      = QColor("#000000")
        self._brush_size = 6
        self._tool       = "pen"
        self._drawing    = False
        self._last_point = QPoint()
        self._pixmap     = None
        self._undo_stack = []
        self._cursor_pos = QPoint(-999, -999)
        self._inside     = False
        self._dimmed     = False
        self.setMouseTracking(True)
        self._update_cursor()

    def _update_cursor(self):
        if self._tool == "pen":
            self.setCursor(make_cursor("pencil.png", 32, 0, 0))
        elif self._tool == "eraser":
            self.setCursor(make_cursor("eraser.png", 32, 0, 0))
        elif self._tool == "fill":
            self.setCursor(make_cursor("bucket.png", 32, 0, 0))
        elif self._tool == "eyedropper":
            self.setCursor(make_cursor("pin.png", 32, 0, 0))
        else:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def resizeEvent(self, event):
        if self._pixmap is None or self._pixmap.size() != self.size():
            new_px = QPixmap(self.size())
            new_px.fill(QColor("#FFFFFF"))
            if self._pixmap:
                p = QPainter(new_px)
                p.drawPixmap(0, 0, self._pixmap)
                p.end()
            self._pixmap = new_px
        super().resizeEvent(event)

    def set_color(self, color: QColor): self._color = color
    def set_brush_size(self, size: int): self._brush_size = size
    def set_tool(self, tool: str):
        self._tool = tool
        self._update_cursor()

    def set_dimmed(self, dimmed: bool):
        self._dimmed = dimmed
        self.update()

    def clear(self):
        if self._pixmap:
            self._save_undo()
            self._pixmap.fill(QColor("#FFFFFF"))
            self.update()

    def undo(self):
        if self._undo_stack:
            self._pixmap = self._undo_stack.pop()
            self.update()

    def get_pixmap(self) -> QPixmap: return self._pixmap

    def _save_undo(self):
        if self._pixmap:
            self._undo_stack.append(self._pixmap.copy())
            if len(self._undo_stack) > 30:
                self._undo_stack.pop(0)

    def enterEvent(self, event):
        self._inside = True
        self.update()

    def leaveEvent(self, event):
        self._inside = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pt = event.position().toPoint()
        self._cursor_pos = pt
        if self._tool == "eyedropper":
            self._pick_color(pt)
            return
        if self._tool == "fill":
            self._save_undo()
            self._flood_fill(pt, self._color)
            return
        self._save_undo()
        self._drawing    = True
        self._last_point = pt
        self._draw_dot(pt)
        self.update()
        self._draw_line(pt, pt)

    def mouseMoveEvent(self, event):
        pt = event.position().toPoint()
        self._cursor_pos = pt
        if self._drawing and self._pixmap is not None:
            self._draw_line(self._last_point, pt)
            self._last_point = pt
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = False
            self._update_cursor()
            self.update()

    def _draw_dot(self, pt: QPoint):
        if not self._pixmap:
            return
        p = QPainter(self._pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._tool == "eraser":
            r, color = self._brush_size, QColor("#FFFFFF")
        else:
            r, color = self._brush_size // 2, self._color
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color))
        p.drawEllipse(pt, r, r)
        p.end()
        self.update()

    def _draw_line(self, p1: QPoint, p2: QPoint):
        p = QPainter(self._pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._tool == "eraser":
            pen = QPen(QColor("#FFFFFF"), self._brush_size * 2,
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
        else:
            pen = QPen(self._color, self._brush_size,
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(p1, p2)
        p.end()
        self.update()

    def _pick_color(self, pt: QPoint):
        if self._pixmap:
            img   = self._pixmap.toImage()
            color = QColor(img.pixel(pt.x(), pt.y()))
            self.colour_picked.emit(color)

    def _flood_fill(self, pt: QPoint, fill_color: QColor):
        if not self._pixmap:
            return
        img = self._pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w, h = img.width(), img.height()
        x, y = pt.x(), pt.y()
        if not (0 <= x < w and 0 <= y < h):
            return
        target = QColor(img.pixel(x, y))
        fr, fg, fb = fill_color.red(), fill_color.green(), fill_color.blue()
        if target.red() == fr and target.green() == fg and target.blue() == fb:
            return
        TOLERANCE = 70
        def similar(c: QColor) -> bool:
            return (abs(c.red()   - target.red())   <= TOLERANCE and
                    abs(c.green() - target.green()) <= TOLERANCE and
                    abs(c.blue()  - target.blue())  <= TOLERANCE)
        visited  = set()
        stack    = [(x, y)]
        fill_val = fill_color.rgb()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited: continue
            if not (0 <= cx < w and 0 <= cy < h): continue
            if not similar(QColor(img.pixel(cx, cy))): continue
            visited.add((cx, cy))
            img.setPixel(cx, cy, fill_val)
            stack.extend([(cx+1,cy),(cx-1,cy),(cx,cy+1),(cx,cy-1)])
        self._pixmap = QPixmap.fromImage(img)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        else:
            p.fillRect(self.rect(), QColor("#FFFFFF"))

        show_circle = self._inside and self._tool in ("pen", "fill", "eraser")
        if show_circle:
            r      = self._brush_size // 2 if self._tool != "eraser" else self._brush_size
            cx, cy = self._cursor_pos.x(), self._cursor_pos.y()
            fill   = self._color if self._tool != "eraser" else QColor("#FFFFFF")
            stroke = QColor(0, 0, 0, int(255 * 0.35))
            p.setBrush(QBrush(fill))
            p.setPen(QPen(stroke, 2))
            p.drawEllipse(QPoint(cx, cy), r, r)

        if self._inside and self._tool == "eyedropper" and self._pixmap:
            cx, cy = self._cursor_pos.x(), self._cursor_pos.y()
            img    = self._pixmap.toImage()
            sx     = max(0, min(cx, img.width()-1))
            sy     = max(0, min(cy, img.height()-1))
            hc     = QColor(img.pixel(sx, sy))
            stroke = QColor(0, 0, 0, int(255 * 0.35))
            p.setBrush(QBrush(hc))
            p.setPen(QPen(stroke, 2))
            p.drawEllipse(QPoint(cx + 14, cy - 14), 10, 10)

        # Dim overlay when submitted
        if self._dimmed:
            p.setBrush(QBrush(QColor(0, 0, 0, 100)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(self.rect())


# ── Colour swatch ──────────────────────────────────────────────────────────────
class ColourSwatch(QPushButton):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color    = color
        self._selected = False
        self.setFixedSize(42, 42)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._apply_style()

    def set_selected(self, v: bool):
        self._selected = v
        self._apply_style()

    def set_color(self, hex_color: str):
        self._color = hex_color
        self._apply_style()

    def color(self) -> QColor:
        return QColor(self._color)

    def _apply_style(self):
        border = "3px solid #FFFFFF" if self._selected else "2px solid rgba(255,255,255,0.25)"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._color};
                border: {border};
                border-radius: 6px;
            }}
            QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.8); }}
        """)


# ── Tool button ────────────────────────────────────────────────────────────────
class ToolButton(QPushButton):
    def __init__(self, icon: str, tooltip: str, size: int = 66, checkable: bool = True, parent=None):
        super().__init__(icon, parent)
        self.setFixedSize(size, size)
        self.setToolTip(tooltip)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setCheckable(checkable)
        self._red = False
        self._apply_style()

    def set_red(self, red: bool):
        self._red = red
        self._apply_style()

    def _apply_style(self):
        if self._red:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(239,68,68,0.75);
                    border: 2px solid rgba(239,68,68,0.4);
                    border-radius: 10px;
                    color: {TEXT_LIGHT};
                    font-size: 20px;
                }}
                QPushButton:hover {{ background: rgba(239,68,68,0.95); }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {TOOL_BG};
                    border: 2px solid {BORDER};
                    border-radius: 10px;
                    color: {TEXT_LIGHT};
                    font-size: 20px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.25);
                    border: 2px solid {BORDER_HOV};
                }}
                QPushButton:checked {{
                    background: {TOOL_ACTIVE};
                    border: 2px solid rgba(255,255,255,0.9);
                }}
            """)


# ── Timer ring ─────────────────────────────────────────────────────────────────
class TimerRing(QWidget):
    def __init__(self, seconds: int = 60, panic_secs: int = 15,
                 panic_mode: bool = True, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self._total       = seconds
        self._remaining   = seconds
        self._panic_secs  = panic_secs
        self._panic_mode  = panic_mode
        self._in_panic    = False
        self._timer       = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self):  self._timer.start()
    def stop(self):
        self._timer.stop()
        self._stop_panic()

    def reset(self, seconds: int = None):
        self._timer.stop()
        self._stop_panic()
        if seconds: self._total = seconds
        self._remaining = self._total
        self._in_panic  = False
        self.update()

    def _tick(self):
        if self._remaining > 0:
            self._remaining -= 1
            # Check panic trigger
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
            import os
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "assets", "music", "clock_ticking.mp3"
            )
            mx.music.load(path)
            mx.music.play(-1)  # loop
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
        p.setPen(QPen(QColor(255,255,255,40), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
        ratio = self._remaining / self._total if self._total > 0 else 0
        # Panic = red, low but not panic = orange, normal = green
        if self._in_panic:
            color = QColor("#EF4444")
        elif ratio <= 0.3:
            color = QColor("#F97316")
        else:
            color = QColor("#A3E635")
        p.setPen(QPen(color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 90*16, -int(ratio*360*16))
        p.setPen(color if self._in_panic else QColor(TEXT_LIGHT))
        f = QFont(); f.setPointSize(13); f.setBold(True); p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._remaining))


class DrawScreen(QWidget):
    done_clicked   = pyqtSignal(QPixmap)
    back_requested = pyqtSignal()
    saved          = pyqtSignal(dict)
    edit_requested = pyqtSignal()   # player wants to re-edit after submitting

    def __init__(self, prompt: str = "Draw something amazing!",
                 round_str: str = "1/3", seconds: int = 60,
                 panic_mode: bool = True, panic_secs: int = 15,
                 submit_once: bool = False, parent=None):
        super().__init__(parent)
        self._prompt      = prompt
        self._round_str   = round_str
        self._seconds     = seconds
        self._panic_mode  = panic_mode
        self._panic_secs  = panic_secs
        self._submit_once = submit_once
        self._active_swatch  = None
        self._picker_popup   = None
        self.setStyleSheet("background: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._build_ui()
        self.setFocus()

    def set_prompt(self, prompt: str):
        self._prompt = prompt
        self._prompt_label.setText(f"✏  {prompt}")

    def start_timer(self):
        self._timer_ring.start()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        from app import scale as ui_scale
        S = ui_scale.get()
        PAL_W      = int(110 * S)
        TOOL_W     = int(90  * S)
        CANVAS_W   = int(980 * S)
        CANVAS_H   = int(680 * S)
        GAP        = int(10  * S)
        MARGIN     = int(16  * S)
        BAR_H_TOP  = int(64  * S)
        BAR_H_BOT  = int(76  * S)

        inner_w = MARGIN + PAL_W + GAP + CANVAS_W + GAP + TOOL_W + MARGIN
        inner_h = BAR_H_TOP + GAP + CANVAS_H + GAP + BAR_H_BOT

        self._card = QWidget()
        self._card.setFixedSize(inner_w, inner_h)
        self._card.setStyleSheet("background: transparent;")

        card_root = QVBoxLayout(self._card)
        card_root.setContentsMargins(0, 0, 0, 0)
        card_root.setSpacing(GAP)

        top_bar = self._build_top_bar()
        top_bar.setFixedHeight(BAR_H_TOP)
        top_bar.setFixedWidth(inner_w - MARGIN * 2)
        top_bar.setStyleSheet(f"""
            background: {PANEL_BG};
            border: 1px solid {BORDER};
            border-radius: 12px;
        """)
        card_root.addWidget(top_bar, alignment=Qt.AlignmentFlag.AlignHCenter)

        mid = QWidget()
        mid.setStyleSheet("background: transparent;")
        ml = QHBoxLayout(mid)
        ml.setContentsMargins(MARGIN, 0, MARGIN, 0)
        ml.setSpacing(GAP)
        ml.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pal = self._build_palette(S)
        pal.setFixedWidth(PAL_W)
        canvas = self._build_canvas(CANVAS_W, CANVAS_H)
        tools = self._build_tools(S)
        tools.setFixedWidth(TOOL_W)

        ml.addWidget(pal,    stretch=0)
        ml.addWidget(canvas, stretch=0)
        ml.addWidget(tools,  stretch=0)
        card_root.addWidget(mid, stretch=1)

        bot_bar = self._build_bottom_bar()
        bot_bar.setFixedHeight(BAR_H_BOT)
        bot_bar.setFixedWidth(inner_w - MARGIN * 2)
        bot_bar.setStyleSheet(f"""
            background: rgba(0,0,0,0.18);
            border: 1px solid {BORDER};
            border-radius: 12px;
        """)
        card_root.addWidget(bot_bar, alignment=Qt.AlignmentFlag.AlignHCenter)

        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: rgba(0,0,0,0.18); border: none;")
        l = QHBoxLayout(bar)
        l.setContentsMargins(16, 0, 16, 0)
        l.setSpacing(12)

        if not self._round_str:
            leave_btn = QPushButton("← LEAVE")
            leave_btn.setFixedHeight(40)
            leave_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            leave_btn.clicked.connect(self.back_requested)
            leave_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(239,68,68,0.70);
                    border: 2px solid rgba(239,68,68,0.4);
                    border-radius: 20px;
                    color: {TEXT_LIGHT};
                    font-size: 14px;
                    font-weight: 800;
                    letter-spacing: 2px;
                    padding: 0 18px;
                }}
                QPushButton:hover {{ background: rgba(239,68,68,0.95); }}
            """)
            l.addWidget(leave_btn)
        else:
            rnd = QLabel(self._round_str)
            rnd.setFixedWidth(60)
            rnd.setStyleSheet(f"color:{TEXT_LIGHT}; font-size:18px; font-weight:900;")
            l.addWidget(rnd)

        self._prompt_label = QLabel(f"✏  {self._prompt}")
        self._prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prompt_label.setWordWrap(True)
        self._prompt_label.setStyleSheet(
            f"color:{TEXT_LIGHT}; font-size:35px; font-weight:900; letter-spacing:1px; background:transparent;")

        self._timer_ring = TimerRing(
            self._seconds,
            panic_secs=self._panic_secs,
            panic_mode=self._panic_mode,
        )

        l.addWidget(self._prompt_label, stretch=1)

        # Submission count — right side, left of timer ring
        if self._round_str:
            self._submit_lbl = QLabel("")
            self._submit_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._submit_lbl.setStyleSheet(f"""
                color: #FFFFFF;
                font-size: 20px;
                font-weight: 900;
                background: transparent;
            """)
            self._submit_lbl.setVisible(False)
            l.addWidget(self._submit_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        l.addWidget(self._timer_ring)
        return bar

    def _build_palette(self, S: float = 1.0) -> QWidget:
        panel = QWidget()
        panel.setObjectName("pal")
        panel.setStyleSheet(f"""
            QWidget#pal {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)
        sw = int(42 * S)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(int(6*S), int(8*S), int(6*S), int(8*S))
        layout.setSpacing(int(4*S))
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        self._swatches = []
        pairs = [PALETTE[i:i+2] for i in range(0, len(PALETTE), 2)]
        for pair in pairs:
            row = QHBoxLayout()
            row.setSpacing(int(4*S))
            row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            for hex_c in pair:
                s = ColourSwatch(hex_c)
                s.setFixedSize(sw, sw)
                s.clicked.connect(lambda _, sw_=s: self._select_swatch(sw_))
                self._swatches.append(s)
                row.addWidget(s)
            layout.addLayout(row)

        layout.addSpacing(int(4*S))

        cw = int(96 * S)
        ch = int(42 * S)
        self._custom_swatch = ColourSwatch("#000000")
        self._custom_swatch.setFixedSize(cw, ch)
        self._custom_swatch.setToolTip("Custom colour")
        self._custom_swatch.setText("＋")
        self._custom_swatch.setStyleSheet(f"""
            QPushButton {{
                background: #000000;
                border: 3px solid rgba(255,255,255,0.8);
                border-radius: 6px;
                color: white;
                font-size: {int(14*S)}px;
                font-weight: 800;
            }}
            QPushButton:hover {{ border: 3px solid #FFFFFF; }}
        """)
        self._custom_swatch.clicked.connect(self._open_colour_picker)
        layout.addWidget(self._custom_swatch, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._swatches[0].set_selected(True)
        self._active_swatch = self._swatches[0]
        # Sync custom swatch to initial colour (black)
        self._update_custom_swatch_color(self._swatches[0].color())
        return panel

    def _build_canvas(self, w: int = 620, h: int = 460) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("cw")
        wrapper.setStyleSheet("""
            QWidget#cw {
                background: #FFFFFF;
                border: 2px solid rgba(255,255,255,0.6);
                border-radius: 10px;
            }
        """)
        wrapper.setFixedSize(w, h)
        l = QVBoxLayout(wrapper)
        l.setContentsMargins(2, 2, 2, 2)
        self._canvas = DrawingCanvas()
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._canvas.colour_picked.connect(self._on_colour_picked)
        l.addWidget(self._canvas)
        return wrapper

    def _build_tools(self, S: float = 1.0) -> QWidget:
        panel = QWidget()
        panel.setObjectName("tools")
        panel.setStyleSheet(f"""
            QWidget#tools {{
                background: {PANEL_BG};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)
        l = QVBoxLayout(panel)
        l.setContentsMargins(0, int(10*S), 0, int(10*S))
        l.setSpacing(int(6*S))
        l.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        icon_sz = int(40 * S)
        btn_sz  = int(66 * S)

        self._pen_btn   = ToolButton("", "Pen  [B]",           btn_sz)
        self._erase_btn = ToolButton("", "Eraser  [E]",        btn_sz)
        self._fill_btn  = ToolButton("", "Fill  [F]",          btn_sz)
        self._eye_btn   = ToolButton("", "Colour picker  [C]", btn_sz)

        for btn, icon_name in [
            (self._pen_btn,   "pencil.png"),
            (self._erase_btn, "eraser.png"),
            (self._fill_btn,  "bucket.png"),
            (self._eye_btn,   "pin.png"),
        ]:
            px = load_icon(icon_name, icon_sz)
            if not px.isNull():
                btn.setIcon(QIcon(px))
                btn.setIconSize(QSize(icon_sz, icon_sz))

        self._pen_btn.setChecked(True)
        self._pen_btn.clicked.connect(lambda: self._select_tool("pen",        self._pen_btn))
        self._erase_btn.clicked.connect(lambda: self._select_tool("eraser",   self._erase_btn))
        self._fill_btn.clicked.connect(lambda: self._select_tool("fill",      self._fill_btn))
        self._eye_btn.clicked.connect(lambda: self._select_tool("eyedropper", self._eye_btn))

        self._tool_group = QButtonGroup(self)
        for b in [self._pen_btn, self._erase_btn, self._fill_btn, self._eye_btn]:
            self._tool_group.addButton(b)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background: {BORDER}; max-height:1px; border:none;")

        self._undo_btn = ToolButton("", "Undo  [Ctrl+Z]", btn_sz, checkable=False)
        back_px = load_icon("back.png", icon_sz)
        if not back_px.isNull():
            self._undo_btn.setIcon(QIcon(back_px))
            self._undo_btn.setIconSize(QSize(icon_sz, icon_sz))
        self._undo_btn.clicked.connect(self._canvas.undo)

        self._clear_btn = ToolButton("", "Clear canvas", btn_sz, checkable=False)
        self._clear_btn.set_red(True)
        trash_px = load_icon("trash.png", icon_sz)
        if not trash_px.isNull():
            self._clear_btn.setIcon(QIcon(trash_px))
            self._clear_btn.setIconSize(QSize(icon_sz, icon_sz))
        self._clear_btn.clicked.connect(self._confirm_clear)

        l.addWidget(self._pen_btn,   alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(self._erase_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(self._fill_btn,  alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(self._eye_btn,   alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(div)
        l.addWidget(self._undo_btn,  alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(self._clear_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        return panel

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: rgba(0,0,0,0.18); border: none;")
        l = QHBoxLayout(bar)
        l.setContentsMargins(16, 10, 16, 10)
        l.setSpacing(10)

        self._size_btns = []
        for size in BRUSH_SIZES:
            btn = QPushButton()
            d   = max(8, int(size * 1.4))
            btn.setFixedSize(d+10, d+10)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.45);
                    border: 2px solid {BORDER};
                    border-radius: {(d+10)//2}px;
                }}
                QPushButton:hover {{ background: rgba(255,255,255,0.85); }}
                QPushButton:checked {{
                    background: #FFFFFF;
                    border: 2px solid #FFFFFF;
                }}
            """)
            btn.clicked.connect(lambda _, s=size, b=btn: self._select_size(s, b))
            l.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)
            self._size_btns.append((size, btn))

        self._size_btns[1][1].setChecked(True)
        self._canvas.set_brush_size(BRUSH_SIZES[1])

        l.addStretch()

        if not self._round_str:
            action_btn = QPushButton("💾  SAVE")
            action_btn.clicked.connect(self._on_save)
        else:
            action_btn = QPushButton("✓  DONE")
            action_btn.clicked.connect(self._on_done)

        self._action_btn = action_btn
        action_btn.setFixedHeight(44)
        action_btn.setMinimumWidth(130)
        action_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._apply_action_btn_style(submitted=False)
        l.addWidget(action_btn)
        return bar

    # ── Actions ───────────────────────────────────────────────────────────────

    def _update_custom_swatch_color(self, color: QColor):
        self._custom_swatch.set_color(color.name())
        self._custom_swatch.setStyleSheet(f"""
            QPushButton {{
                background: {color.name()};
                border: 3px solid rgba(255,255,255,0.8);
                border-radius: 6px;
            }}
            QPushButton:hover {{ border: 3px solid #FFFFFF; }}
        """)

    def _select_swatch(self, swatch: ColourSwatch):
        if self._active_swatch:
            self._active_swatch.set_selected(False)
        swatch.set_selected(True)
        self._active_swatch = swatch
        self._canvas.set_color(swatch.color())
        self._update_custom_swatch_color(swatch.color())
        if self._canvas._tool not in ("pen", "fill"):
            self._select_tool("pen", self._pen_btn)
            self._pen_btn.setChecked(True)

    def _select_tool(self, tool: str, btn: ToolButton = None):
        self._canvas.set_tool(tool)

    def _select_size(self, size: int, btn: QPushButton):
        for _, b in self._size_btns:
            b.setChecked(False)
        btn.setChecked(True)
        self._canvas.set_brush_size(size)

    def _open_colour_picker(self):
        popup = ColourPickerPopup(self)
        popup.colour_selected.connect(self._on_custom_colour)
        popup.set_color(self._canvas._color)
        pos = self._custom_swatch.mapToGlobal(
            QPoint(self._custom_swatch.width() + 4, 0)
        )
        popup.move(pos)
        popup.show()
        self._picker_popup = popup

    def _on_custom_colour(self, color: QColor):
        self._update_custom_swatch_color(color)
        if self._active_swatch:
            self._active_swatch.set_selected(False)
        self._active_swatch = None
        self._canvas.set_color(color)
        if self._canvas._tool not in ("pen", "fill"):
            self._select_tool("pen", self._pen_btn)
            self._pen_btn.setChecked(True)

    def _on_colour_picked(self, color: QColor):
        self._on_custom_colour(color)
        self._select_tool("pen", self._pen_btn)
        self._pen_btn.setChecked(True)

    def _on_save(self):
        try:
            px = self._canvas.get_pixmap()
            if not px:
                return
            from app.screens.photos import save_drawing
            entry = save_drawing(px)
            self.saved.emit(entry)
            orig = self._prompt_label.text()
            self._prompt_label.setText("✓  Saved!")
            QTimer.singleShot(1500, lambda: self._prompt_label.setText(orig))
        except Exception as e:
            print(f"[Save error] {e}")

    def _confirm_clear(self):
        from PyQt6.QtWidgets import QMessageBox
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Clear Canvas")
        dlg.setText("Are you sure you want to delete everything on the canvas?")
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        dlg.setStyleSheet(f"""
            QMessageBox {{ background: #0EA5E9; }}
            QMessageBox QLabel {{ color:#FFFFFF; font-size:15px; font-weight:600; }}
            QPushButton {{
                background: rgba(0,0,0,0.25);
                border: 2px solid rgba(255,255,255,0.45);
                border-radius: 10px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
                padding: 6px 24px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: rgba(0,0,0,0.40);
                border: 2px solid rgba(255,255,255,0.85);
            }}
        """)
        if dlg.exec() == QMessageBox.StandardButton.Yes:
            self._canvas.clear()

    def _apply_action_btn_style(self, submitted: bool):
        if submitted:
            self._action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.20);
                    border: 2px solid rgba(255,255,255,0.50);
                    border-radius: 22px;
                    color: #FFFFFF;
                    font-size: 15px;
                    font-weight: 800;
                    letter-spacing: 2px;
                    padding: 0 20px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.30);
                    border: 2px solid rgba(255,255,255,0.80);
                }}
            """)
        else:
            self._action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ORANGE};
                    border: 3px solid rgba(249,115,22,0.4);
                    border-radius: 22px;
                    color: #FFFFFF;
                    font-size: 15px;
                    font-weight: 800;
                    letter-spacing: 2px;
                    padding: 0 20px;
                }}
                QPushButton:hover {{ background: {ORANGE_HOV}; }}
            """)

    def set_submission_count(self, submitted: int, total: int):
        """Called by window.py to update the waiting label."""
        if hasattr(self, "_submit_lbl"):
            self._submit_lbl.setText(f"{submitted} / {total} submitted")
            self._submit_lbl.setVisible(True)

    def _on_done(self):
        if getattr(self, "_submitted", False):
            # Edit mode — only allowed if submit_once is off
            if self._submit_once:
                return   # ignore click, no editing allowed
            self._submitted = False
            self._action_btn.setText("✓  DONE")
            self._apply_action_btn_style(submitted=False)
            self._canvas.set_dimmed(False)
            self._canvas.setEnabled(True)
            self._undo_btn.setEnabled(True)
            self.edit_requested.emit()
        else:
            # Submit
            self._submitted = True
            self._action_btn.setText("✏  EDIT")
            self._apply_action_btn_style(submitted=True)
            self._canvas.set_dimmed(True)
            self._canvas.setEnabled(False)
            self._undo_btn.setEnabled(False)
            px = self._canvas.get_pixmap()
            self.done_clicked.emit(px if px else QPixmap())

    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier:
            if not getattr(self, "_submitted", False):
                self._canvas.undo()
            return
        if key == Qt.Key.Key_B:
            self._select_tool("pen", self._pen_btn)
            self._pen_btn.setChecked(True)
            self._erase_btn.setChecked(False)
            self._fill_btn.setChecked(False)
            self._eye_btn.setChecked(False); return
        if key == Qt.Key.Key_E:
            self._select_tool("eraser", self._erase_btn)
            self._erase_btn.setChecked(True)
            self._pen_btn.setChecked(False)
            self._fill_btn.setChecked(False)
            self._eye_btn.setChecked(False); return
        if key == Qt.Key.Key_F:
            self._select_tool("fill", self._fill_btn)
            self._fill_btn.setChecked(True)
            self._pen_btn.setChecked(False)
            self._erase_btn.setChecked(False)
            self._eye_btn.setChecked(False); return
        if key == Qt.Key.Key_C:
            self._select_tool("eyedropper", self._eye_btn)
            self._eye_btn.setChecked(True)
            self._pen_btn.setChecked(False)
            self._erase_btn.setChecked(False)
            self._fill_btn.setChecked(False); return
        super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    class _BG(QWidget):
        def __init__(self):
            super().__init__()
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "assets", "background", "default.png"
            )
            self._px = QPixmap(path)

        def paintEvent(self, event):
            p = QPainter(self)
            if self._px.isNull():
                p.fillRect(self.rect(), QColor(BG))
                return
            sw, sh = self.width(), self.height()
            iw, ih = self._px.width(), self._px.height()
            scale  = max(sw / iw, sh / ih)
            dw, dh = int(iw * scale), int(ih * scale)
            x, y   = (sw - dw) // 2, (sh - dh) // 2
            scaled = self._px.scaled(dw, dh,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(x, y, scaled)

    # Bootstrap scale for standalone run
    try:
        from app import scale as ui_scale
    except ImportError:
        class ui_scale:
            @staticmethod
            def get(): return 1.0

    w = QMainWindow()
    w.setMinimumSize(1282, 890)
    w.resize(1282, 890)

    bg = _BG()
    w.setCentralWidget(bg)

    layout = QVBoxLayout(bg)
    layout.setContentsMargins(0, 0, 0, 0)

    screen = DrawScreen(prompt="A cat riding a bicycle", round_str="1/3", seconds=60)
    layout.addWidget(screen, alignment=Qt.AlignmentFlag.AlignCenter)

    screen.done_clicked.connect(lambda px: print("Done!"))
    w.show()
    sys.exit(app.exec())