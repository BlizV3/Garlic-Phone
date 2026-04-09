import sys
import socket
import asyncio
import threading

from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QApplication, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QColor, QPixmap, QPainter, QCursor

from app.screens.home   import HomeScreen
from app.screens.create import CreateScreen
from app.screens.lobby  import LobbyScreen
from app.backend.client import GameClient
from app.backend        import messages as msg
from app.style.sounds   import SoundManager


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MainWindow(QMainWindow):
    _sig_room_created      = pyqtSignal(dict)
    _sig_room_joined       = pyqtSignal(dict)
    _sig_player_joined     = pyqtSignal(dict)
    _sig_player_left       = pyqtSignal(dict)
    _sig_error             = pyqtSignal(dict)
    _sig_host_disconnected = pyqtSignal()
    _sig_phase_changed     = pyqtSignal(dict)
    _sig_show_results      = pyqtSignal(dict)
    _sig_host_decision     = pyqtSignal()
    _sig_submission_ack    = pyqtSignal(dict)
    _sig_host_next         = pyqtSignal()
    _sig_game_error        = pyqtSignal(dict)
    _sig_room_list         = pyqtSignal(dict)
    _sig_browser_connected = pyqtSignal()
    _sig_browser_error     = pyqtSignal()
    _sig_kicked            = pyqtSignal(dict)
    _sig_kicked            = pyqtSignal(dict)

    PORT     = 8765
    ASPECT_W = 1282
    ASPECT_H = 890

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Garlic Phone")

        # ── Calculate window size from monitor at 75% coverage ─────────────
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            mon_w, mon_h = sg.width(), sg.height()
        else:
            mon_w, mon_h = 1920, 1080

        # Fit a 1282:890 rect into 75% of the monitor
        target_w = int(mon_w * 0.75)
        target_h = int(mon_h * 0.75)
        scale    = min(target_w / self.ASPECT_W, target_h / self.ASPECT_H)
        win_w    = int(self.ASPECT_W * scale)
        win_h    = int(self.ASPECT_H * scale)

        # Store scale so screens can use it
        self._ui_scale = scale

        # Set global scale so all screens can read it
        from app import scale as ui_scale
        ui_scale.set_scale(scale)

        self.setMinimumSize(win_w, win_h)
        self.resize(win_w, win_h)
        self.setStyleSheet("background: transparent;")

        # ── State ─────────────────────────────────────────────────────────
        self._client          = None
        self._is_host         = False
        self._my_id           = ""
        self._my_username     = ""
        self._lobby           = None
        self._draw_screen     = None
        self._write_screen    = None
        self._photos_screen   = None
        self._results_screen  = None
        self._game_settings   = {}
        self._in_game_phase   = False
        self._gear_visible    = True
        self._browser_client  = None
        self._pending_code    = ""
        self._pending_req_code = False
        self._pending_password = ""
        self._custom_code     = ""
        self._toast           = None
        self._pending_password = ""
        self._lobby_players   = {}   # player_id → {username, is_host, avatar}
        self._max_players     = 8
        self._require_code    = True
        self._pending_code    = ""
        self._avatar_b64      = ""
        self._server_loop     = None
        self._sfx             = SoundManager()
        self._fullscreen_mode = False

        # ── Background widget ──────────────────────────────────────────────
        import os
        class BackgroundWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                from app.paths import asset
                path = asset("background", "default.png")
                self._bg = QPixmap(path)

            def paintEvent(self, event):
                p = QPainter(self)
                if self._bg.isNull():
                    p.fillRect(self.rect(), QColor("#0EA5E9"))
                    return
                sw, sh = self.width(), self.height()
                iw, ih = self._bg.width(), self._bg.height()
                scale  = max(sw / iw, sh / ih)
                dw, dh = int(iw * scale), int(ih * scale)
                x, y   = (sw - dw) // 2, (sh - dh) // 2
                scaled = self._bg.scaled(dw, dh,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(x, y, scaled)

        outer = BackgroundWidget()
        self.setCentralWidget(outer)
        self._outer_layout = QVBoxLayout(outer)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)

        # ── Stack + wrapper ────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        self._wrapper = QWidget()
        self._wrapper.setStyleSheet("background: transparent;")
        wl = QVBoxLayout(self._wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(self._stack)

        self._outer_layout.addWidget(self._wrapper, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── Floating ⚙ button (always top-right of outer) ─────────────────
        self._gear_btn = QPushButton("⚙", outer)
        self._gear_btn.setFixedSize(48, 48)
        self._gear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._gear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0,0,0,0.40);
                border: 1px solid rgba(255,255,255,0.35);
                border-radius: 24px;
                color: #FFFFFF;
                font-size: 22px;
            }
            QPushButton:hover {
                background: rgba(0,0,0,0.60);
                border: 1px solid rgba(255,255,255,0.7);
            }
        """)
        self._gear_btn.clicked.connect(self._toggle_settings)
        self._gear_btn.raise_()

        # Opacity effect + animation for proximity fade
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        self._gear_opacity = QGraphicsOpacityEffect(self._gear_btn)
        self._gear_opacity.setOpacity(1.0)
        self._gear_btn.setGraphicsEffect(self._gear_opacity)

        self._gear_anim = QPropertyAnimation(self._gear_opacity, b"opacity")
        self._gear_anim.setDuration(250)
        self._gear_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._gear_visible  = True   # current logical state
        self._in_game_phase = False  # True when draw/write screens are active

        # Track mouse over the outer widget
        outer.setMouseTracking(True)
        outer.mouseMoveEvent = self._on_outer_mouse_move

        # ── Floating settings panel (parented to outer) ────────────────────
        from app.screens.settings import SettingsPanel
        self._settings_panel = SettingsPanel(self._sfx, parent=outer)
        self._settings_panel.window_mode.connect(self._on_window_mode)
        self._settings_panel.test_requested.connect(self._on_test_mode)
        self._settings_panel.hide()

        # ── Screens ───────────────────────────────────────────────────────
        from app.screens.server_browser import ServerBrowserScreen
        from app.screens.profile import ProfileScreen

        self.home_screen    = HomeScreen()
        self.create_screen  = CreateScreen()
        self.browser_screen = ServerBrowserScreen()
        self.profile_screen = ProfileScreen()

        self._stack.addWidget(self.home_screen)
        self._stack.addWidget(self.create_screen)
        self._stack.addWidget(self.browser_screen)
        self._stack.addWidget(self.profile_screen)

        # ── Screen signals ─────────────────────────────────────────────────
        self.home_screen.create_clicked.connect(self._go_create)
        self.home_screen.join_clicked.connect(self._go_browser)
        self.home_screen.free_draw_clicked.connect(self._go_free_draw)
        self.home_screen.photos_clicked.connect(self._go_photos)
        self.create_screen.back_requested.connect(self._go_home)
        self.create_screen.create_requested.connect(self._on_create_requested)
        self.browser_screen.back_requested.connect(self._go_home)
        self.browser_screen.join_requested.connect(self._on_room_selected)
        self.browser_screen.code_join.connect(self._on_code_join)
        self.browser_screen.refresh_needed.connect(self._refresh_rooms)
        self.profile_screen.back_requested.connect(self._go_browser)
        self.profile_screen.confirmed.connect(self._on_profile_confirmed)

        # ── Backend signals ────────────────────────────────────────────────
        self._sig_room_created.connect(self._on_room_created)
        self._sig_room_joined.connect(self._on_room_joined)
        self._sig_player_joined.connect(self._on_player_joined)
        self._sig_player_left.connect(self._on_player_left)
        self._sig_error.connect(self._on_error)
        self._sig_host_disconnected.connect(self._on_host_disconnected)
        self._sig_phase_changed.connect(self._on_phase_changed)
        self._sig_show_results.connect(self._on_show_results)
        self._sig_submission_ack.connect(self._on_submission_ack)
        self._sig_host_decision.connect(self._on_host_decision)
        self._sig_host_next.connect(self._on_host_next)
        self._sig_game_error.connect(self._on_game_error)
        self._sig_room_list.connect(self._on_room_list)
        self._sig_browser_connected.connect(self._do_request_rooms)
        self._sig_browser_error.connect(lambda: self.browser_screen.set_status("Server unavailable — try refreshing"))
        self._sig_kicked.connect(self._on_kicked)
        self._sig_kicked.connect(self._on_kicked)

        self._go_home()
        self._sfx.play_music_home()

    def _on_outer_mouse_move(self, event):
        """Show gear when mouse is within 100px of the gear button centre."""
        if not self._in_game_phase:
            return
        pos    = event.position().toPoint()
        btn_cx = self._gear_btn.x() + self._gear_btn.width()  // 2
        btn_cy = self._gear_btn.y() + self._gear_btn.height() // 2
        dist   = ((pos.x() - btn_cx) ** 2 + (pos.y() - btn_cy) ** 2) ** 0.5
        should_show = dist < 100
        if should_show != self._gear_visible:
            self._set_gear_visible(should_show)

    def _set_gear_visible(self, visible: bool):
        if visible == self._gear_visible:
            return
        self._gear_visible = visible
        self._gear_anim.stop()
        self._gear_anim.setStartValue(self._gear_opacity.opacity())
        self._gear_anim.setEndValue(1.0 if visible else 0.0)
        self._gear_anim.start()
        if visible:
            self._gear_btn.raise_()

    def _enter_game_phase(self):
        """Called when navigating into draw/write screens."""
        self._in_game_phase = True
        self._set_gear_visible(False)
        self._gear_visible = False  # force state so next move triggers correctly

    def _leave_game_phase(self):
        """Called when leaving draw/write screens."""
        self._in_game_phase = False
        self._gear_opacity.setOpacity(1.0)
        self._gear_visible = True
        self._gear_btn.raise_()

    # ── Resize / aspect ratio ──────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_aspect_ratio()
        self._reposition_overlays()

    def _apply_aspect_ratio(self):
        cw = self.centralWidget()
        if not cw:
            return
        w, h = cw.width(), cw.height()
        if getattr(self, "_fullscreen_mode", False):
            self._wrapper.setFixedSize(w, h)
            return
        tw = w
        th = int(w * self.ASPECT_H / self.ASPECT_W)
        if th > h:
            th = h
            tw = int(h * self.ASPECT_W / self.ASPECT_H)
        self._wrapper.setFixedSize(tw, th)

    def _reposition_overlays(self):
        cw = self.centralWidget()
        if not cw:
            return
        margin = 16
        # Gear button — top-right
        self._gear_btn.move(
            cw.width() - self._gear_btn.width() - margin,
            margin
        )
        # Settings panel — below gear button
        pw = self._settings_panel.width()
        ph = self._settings_panel.height()
        self._settings_panel.move(
            cw.width() - pw - margin,
            margin + self._gear_btn.height() + 6
        )

    def _set_fullscreen_mode(self, enabled: bool):
        self._fullscreen_mode = enabled
        self._apply_aspect_ratio()

    # ── Settings toggle ────────────────────────────────────────────────────

    def _toggle_settings(self):
        if self._settings_panel.isVisible():
            self._settings_panel.hide()
        else:
            self._reposition_overlays()
            self._settings_panel.show()
            self._settings_panel.raise_()
            self._gear_btn.raise_()

    def _on_test_mode(self):
        """Launch a solo single-player test session — always uses local server."""
        self._is_host      = True
        self._my_username  = "Tester"
        self._max_players  = 1
        self._require_code = False
        self._avatar_b64   = ""
        self._test_mode    = True
        self._start_server()   # always local for test mode
        QTimer.singleShot(600, lambda: self._connect_client("127.0.0.1", is_host=True, test_mode=True))

    def _on_window_mode(self, mode: str):
        if mode == "fullscreen":
            self.showFullScreen()
        elif mode == "borderless":
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.showMaximized()
        else:  # windowed
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
            self.showNormal()
            self.resize(self.ASPECT_W, self.ASPECT_H)

    # ── Navigation ─────────────────────────────────────────────────────────

    def _go_home(self):
        self._set_fullscreen_mode(False)
        self._leave_game_phase()
        if self._browser_client:
            try: self._browser_client.disconnect()
            except: pass
            self._browser_client = None
        self._disconnect_client()
        self._sfx.play_music_home()
        self._stack.setCurrentWidget(self.home_screen)

    def _go_browser(self):
        """Navigate to the server browser and fetch room list."""
        self._sfx.play_music_home()
        self._stack.setCurrentWidget(self.browser_screen)
        # Only connect if not already connected
        if self._browser_client is None:
            self.browser_screen.set_status("Connecting to server...")
            self._connect_browser_client()
        else:
            # Already connected — just refresh
            self.browser_screen.set_status("Searching for servers...")
            self._do_request_rooms()

    def _connect_browser_client(self):
        """Connect a persistent client for browsing rooms."""
        from app.config import RENDER_URL
        from app.backend.client import GameClient
        self._browser_client = GameClient()
        self._browser_client.on(msg.ROOM_LIST, lambda p: self._sig_room_list.emit(p))
        self._browser_client.on(msg.ERROR,     lambda p: self._sig_browser_error.emit())
        self._browser_client.on("connected",   lambda p: self._sig_browser_connected.emit())
        addr = RENDER_URL if RENDER_URL else "127.0.0.1"
        self._browser_client.connect(addr, self.PORT)

    def _do_request_rooms(self):
        if self._browser_client:
            try:
                self._browser_client.request_rooms()
            except Exception:
                self.browser_screen.set_status("Could not fetch servers — try refreshing")

    def _refresh_rooms(self):
        self.browser_screen.set_status("Refreshing...")
        self._do_request_rooms()

    def _on_room_list(self, payload: dict):
        rooms = payload.get("rooms", [])
        self.browser_screen.update_rooms(rooms)

    def _on_room_selected(self, code: str, requires_code: bool):
        """Player clicked a room — prompt password if needed, then go to profile."""
        self._pending_code     = code
        self._pending_req_code = requires_code
        self._pending_password = ""

        if requires_code:
            self._show_password_prompt(code)
        else:
            self._stack.setCurrentWidget(self.profile_screen)

    def _show_password_prompt(self, code: str):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                      QLabel, QLineEdit, QPushButton)
        dlg = QDialog(self)
        dlg.setWindowTitle("Room Password")
        dlg.setMinimumWidth(360)
        dlg.setStyleSheet("background:#0EA5E9;")
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12); layout.setContentsMargins(24, 20, 24, 20)

        lbl = QLabel(f'Room "{code}" requires a password:')
        lbl.setStyleSheet("color:#FFFFFF;font-size:15px;font-weight:700;background:transparent;")
        layout.addWidget(lbl)

        inp = QLineEdit()
        inp.setPlaceholderText("Enter password...")
        inp.setFixedHeight(44)
        inp.setStyleSheet("""
            QLineEdit{background:rgba(255,255,255,0.18);border:2px solid rgba(255,255,255,0.35);
            border-radius:12px;color:#FFFFFF;font-size:16px;font-weight:700;
            padding:0 14px;letter-spacing:2px;}
            QLineEdit:focus{border:2px solid rgba(255,255,255,0.85);}
        """)
        layout.addWidget(inp)

        err_lbl = QLabel("")
        err_lbl.setStyleSheet("color:#FCA5A5;font-size:13px;font-weight:600;background:transparent;")
        err_lbl.setVisible(False)
        layout.addWidget(err_lbl)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setFixedHeight(40)
        cancel.setStyleSheet("QPushButton{background:rgba(0,0,0,0.25);border:none;border-radius:10px;color:#FFF;font-size:13px;font-weight:700;padding:0 18px;}QPushButton:hover{background:rgba(0,0,0,0.45);}")
        cancel.clicked.connect(dlg.reject)
        ok = QPushButton("JOIN  ▶"); ok.setFixedHeight(40)
        ok.setStyleSheet("QPushButton{background:#F97316;border:none;border-radius:10px;color:#FFF;font-size:13px;font-weight:800;padding:0 18px;}QPushButton:hover{background:#FB923C;}")

        def _try():
            pw = inp.text().strip()
            if not pw:
                err_lbl.setText("Please enter a password"); err_lbl.setVisible(True); return
            self._pending_password = pw.upper()
            dlg.accept()

        ok.clicked.connect(_try); inp.returnPressed.connect(_try)
        btn_row.addWidget(cancel); btn_row.addWidget(ok)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._stack.setCurrentWidget(self.profile_screen)

    def _on_kicked(self, payload: dict):
        reason = payload.get("reason", "Host kicked you out the lobby")
        self._disconnect_client()
        self._go_home()
        from PyQt6.QtWidgets import QMessageBox
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Kicked")
        dlg.setText(reason)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
        dlg.setStyleSheet("""
            QMessageBox { background: #0EA5E9; }
            QMessageBox QLabel { color:#FFFFFF; font-size:15px; font-weight:600; }
            QPushButton { background:rgba(239,68,68,0.80); border:none;
                          border-radius:10px; color:#FFFFFF; font-size:13px;
                          font-weight:700; padding:6px 28px; }
        """)
        dlg.exec()

    def _on_code_join(self, code: str):
        """Player typed a code directly."""
        self._pending_code      = code
        self._pending_req_code  = True   # assume code required if typed manually
        self._stack.setCurrentWidget(self.profile_screen)

    def _on_profile_confirmed(self, username: str, avatar_b64: str):
        """Profile done — actually connect and join the room."""
        self._is_host     = False
        self._my_username = username
        self._avatar_b64  = avatar_b64

        # Disconnect browser client
        if self._browser_client:
            try: self._browser_client.disconnect()
            except: pass
            self._browser_client = None

        from app.config import RENDER_URL
        connect_addr = RENDER_URL if RENDER_URL else "127.0.0.1"

        self._client = GameClient()
        self._client.on(msg.ROOM_JOINED,       lambda p: self._sig_room_joined.emit(p))
        self._client.on(msg.PLAYER_JOINED,     lambda p: self._sig_player_joined.emit(p))
        self._client.on(msg.PLAYER_LEFT,       lambda p: self._sig_player_left.emit(p))
        self._client.on(msg.ERROR,             lambda p: self._sig_error.emit(p))
        self._client.on(msg.HOST_DISCONNECTED, lambda p: self._sig_host_disconnected.emit())
        self._client.on(msg.PHASE_CHANGED,     lambda p: self._sig_phase_changed.emit(p))
        self._client.on(msg.SHOW_RESULTS,      lambda p: self._sig_show_results.emit(p))
        self._client.on(msg.HOST_DECISION,     lambda p: self._sig_host_decision.emit())
        self._client.on(msg.SUBMISSION_ACK,    lambda p: self._sig_submission_ack.emit(p))
        self._client.on(msg.HOST_NEXT,         lambda p: self._sig_host_next.emit())
        self._client.on(msg.GAME_ERROR,        lambda p: self._sig_game_error.emit(p))
        self._client.on(msg.ROOM_LIST,         lambda p: self._sig_room_list.emit(p))
        self._client.on(msg.KICKED,            lambda p: self._sig_kicked.emit(p))
        self._client.on("connected",           lambda p: self._on_guest_connected(p))
        self._client.connect(connect_addr, self.PORT)

    def _go_create(self):
        self._sfx.play_click()
        self._sfx.play_music_home()
        self._stack.setCurrentWidget(self.create_screen)

    def _go_lobby(self, is_host, room_code, max_players, require_code):
        if self._lobby:
            self._stack.removeWidget(self._lobby)
            self._lobby.deleteLater()

        self._lobby = LobbyScreen(
            is_host=is_host, room_code=room_code,
            max_players=max_players, require_code=require_code,
        )
        self._lobby.back_requested.connect(self._go_home)
        self._lobby.start_requested.connect(self._on_start_requested)
        self._lobby.kick_requested.connect(self._on_kick_requested)
        self._stack.addWidget(self._lobby)
        self._stack.setCurrentWidget(self._lobby)
        self._set_fullscreen_mode(False)
        self._sfx.play_music_lobby()

        if is_host:
            self._lobby.set_host_ip(get_local_ip())

    def _go_photos(self):
        from app.screens.photos import PhotosScreen
        if hasattr(self, "_photos_screen") and self._photos_screen:
            self._stack.removeWidget(self._photos_screen)
            self._photos_screen.deleteLater()
        self._photos_screen = PhotosScreen()
        self._photos_screen.back_requested.connect(self._go_home)
        self._stack.addWidget(self._photos_screen)
        self._stack.setCurrentWidget(self._photos_screen)

    def _go_free_draw(self):
        self._sfx.play_music_lobby()
        self._go_draw(prompt="Free Draw — no rules!", round_str="", seconds=0)

    def _go_draw(self, prompt="", round_str="1/3", seconds=60):
        from app.screens.draw import DrawScreen
        if self._draw_screen:
            self._stack.removeWidget(self._draw_screen)
            self._draw_screen.deleteLater()
        self._draw_screen = DrawScreen(
            prompt=prompt, round_str=round_str, seconds=seconds,
            panic_mode=self._game_settings.get("panic_mode", True),
            panic_secs=self._game_settings.get("panic_secs", 15),
            submit_once=self._game_settings.get("submit_once", False),
        )
        self._draw_screen.done_clicked.connect(self._on_draw_done)
        self._draw_screen.back_requested.connect(self._go_home)
        self._draw_screen.edit_requested.connect(self._on_draw_edit)
        self._stack.addWidget(self._draw_screen)
        self._stack.setCurrentWidget(self._draw_screen)
        self._set_fullscreen_mode(True)
        self._enter_game_phase()
        self._draw_screen.start_timer()

    def _on_draw_edit(self):
        """Player chose to edit — revoke their submission by sending empty drawing."""
        if self._client:
            self._client.submit_drawing("__revoked__")

    def _on_submission_ack(self, payload: dict):
        submitted = payload.get("submitted", 0)
        total     = payload.get("total", 0)
        if self._draw_screen and self._stack.currentWidget() is self._draw_screen:
            self._draw_screen.set_submission_count(submitted, total)
        if hasattr(self, "_write_screen") and self._write_screen and \
                self._stack.currentWidget() is self._write_screen:
            self._write_screen.set_submission_count(submitted, total)

    def _on_draw_done(self, pixmap):
        self._set_fullscreen_mode(False)
        self._leave_game_phase()
        import base64
        from PyQt6.QtCore import QByteArray, QBuffer

        # Scale down if too large to keep payload manageable
        MAX_DIM = 800
        if pixmap.width() > MAX_DIM or pixmap.height() > MAX_DIM:
            pixmap = pixmap.scaled(
                MAX_DIM, MAX_DIM,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

        ba  = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "JPEG", 85)   # JPEG at 85% — far smaller than PNG
        b64 = base64.b64encode(ba.data()).decode("utf-8")
        if self._client:
            # Use chunked sending — splits automatically if large, sends as one if small
            self._client.submit_drawing_chunked(b64)

    # ── Create flow ────────────────────────────────────────────────────────

    def _on_create_requested(self, max_players, require_code, code, avatar_b64):
        self._is_host      = True
        self._max_players  = max_players
        self._require_code = require_code
        self._custom_code  = code.upper().strip() if code else ""
        self._avatar_b64   = avatar_b64
        self._my_username  = self.create_screen._username_input.text().strip() or "Host"

        from app.config import RENDER_URL
        if RENDER_URL:
            # Show a non-blocking "connecting" message
            self._show_connecting_toast()
            self._connect_client(RENDER_URL, is_host=True)
        else:
            self._start_server()
            QTimer.singleShot(600, lambda: self._connect_client("127.0.0.1", is_host=True))

    def _show_connecting_toast(self):
        """Show a small overlay message while connecting to Render."""
        from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
        if hasattr(self, "_toast") and self._toast:
            self._toast.deleteLater()
        outer = self.centralWidget()
        self._toast = QLabel("Connecting to server, please wait...", outer)
        self._toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast.setStyleSheet("""
            QLabel {
                background: rgba(0,0,0,0.75);
                color: #FFFFFF;
                font-size: 16px;
                font-weight: 700;
                border-radius: 14px;
                padding: 14px 28px;
            }
        """)
        self._toast.adjustSize()
        # Centre it
        self._toast.move(
            (outer.width()  - self._toast.width())  // 2,
            (outer.height() - self._toast.height()) // 2,
        )
        self._toast.show()
        self._toast.raise_()
        # Auto-hide after 6 seconds in case connection is slow
        QTimer.singleShot(6000, self._hide_toast)

    def _hide_toast(self):
        if hasattr(self, "_toast") and self._toast:
            self._toast.hide()
            self._toast.deleteLater()
            self._toast = None

    def _start_server(self):
        from app.backend.server import start_server, reset_server
        reset_server()   # wipe any stale global state before starting fresh
        def run():
            self._server_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._server_loop)
            self._server_loop.run_until_complete(start_server())
        t = threading.Thread(target=run, daemon=True, name="GameServer")
        self._server_thread = t
        t.start()

    def _connect_client(self, host, is_host, test_mode=False):
        self._client = GameClient()
        self._client.on(msg.ROOM_CREATED,      lambda p: self._sig_room_created.emit(p))
        self._client.on(msg.ROOM_JOINED,       lambda p: self._sig_room_joined.emit(p))
        self._client.on(msg.PLAYER_JOINED,     lambda p: self._sig_player_joined.emit(p))
        self._client.on(msg.PLAYER_LEFT,       lambda p: self._sig_player_left.emit(p))
        self._client.on(msg.ERROR,             lambda p: self._sig_error.emit(p))
        self._client.on(msg.HOST_DISCONNECTED, lambda p: self._sig_host_disconnected.emit())
        self._client.on(msg.PHASE_CHANGED,     lambda p: self._sig_phase_changed.emit(p))
        self._client.on(msg.SHOW_RESULTS,      lambda p: self._sig_show_results.emit(p))
        self._client.on(msg.HOST_DECISION,     lambda p: self._sig_host_decision.emit())
        self._client.on(msg.SUBMISSION_ACK,   lambda p: self._sig_submission_ack.emit(p))
        self._client.on(msg.HOST_NEXT,         lambda p: self._sig_host_next.emit())
        self._client.on(msg.GAME_ERROR,        lambda p: self._sig_game_error.emit(p))
        self._client.on(msg.ROOM_LIST,          lambda p: self._sig_room_list.emit(p))
        self._client.on(msg.KICKED,            lambda p: self._sig_kicked.emit(p))
        self._client.connect(host, self.PORT)
        if is_host:
            QTimer.singleShot(400, lambda: self._client.create_room(
                self._my_username if self._my_username else "Host",
                self._avatar_b64,
                test_mode=test_mode,
                max_players=getattr(self, "_max_players", 8),
                requires_code=getattr(self, "_require_code", False),
                custom_code=getattr(self, "_custom_code", ""),
            ))

    # ── Join flow (now handled by browser + profile screens) ──────────────

    def _on_guest_connected(self, _):
        self._client.join_room(
            self._pending_code,
            self._my_username,
            self._avatar_b64,
            password=getattr(self, "_pending_password", ""),
        )

    # ── Backend callbacks ──────────────────────────────────────────────────

    def _on_room_created(self, payload):
        self._hide_toast()
        self._my_id = payload.get("player_id", "")
        self._lobby_players = {
            self._my_id: {"username": self._my_username, "is_host": True}
        }
        self._sfx.play_start()
        self._go_lobby(True, payload.get("code", ""),
                       self._max_players, self._require_code)
        self._lobby.add_player(self._my_username or "Host", is_host=True,
                               pixmap=self._b64_to_pixmap(self._avatar_b64),
                               player_id=self._my_id)

    def _on_room_joined(self, payload):
        self._my_id = payload.get("player_id", "")
        room = payload.get("room", {})
        self._lobby_players = {}
        self._sfx.play_start()
        self._go_lobby(False, room.get("code", ""),
                       room.get("rounds", 8), bool(room.get("code")))
        for pid, pdata in room.get("players", {}).items():
            self._lobby_players[pid] = pdata
            self._lobby.add_player(
                username=pdata.get("username", "?"),
                is_host=pdata.get("is_host", False),
                pixmap=self._b64_to_pixmap(pdata.get("avatar", "")),
                player_id=pid)

    def _on_player_joined(self, payload):
        if self._lobby:
            p = payload.get("player", {})
            pid = p.get("id", "")
            if pid:
                self._lobby_players[pid] = p
            self._sfx.play_join()
            self._lobby.add_player(
                username=p.get("username", "?"),
                is_host=p.get("is_host", False),
                pixmap=self._b64_to_pixmap(p.get("avatar", "")),
                player_id=pid)

    def _on_player_left(self, payload):
        if self._lobby:
            self._sfx.play_click()
            pid = payload.get("player_id", "")
            self._lobby_players.pop(pid, None)
            self._lobby.remove_player(payload.get("username", ""))

    def _on_error(self, payload):
        reason = payload.get("reason", "Unknown error")
        from PyQt6.QtWidgets import QMessageBox
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Error")
        dlg.setText(reason)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
        dlg.setStyleSheet("""
            QMessageBox { background: #0EA5E9; }
            QMessageBox QLabel { color:#FFFFFF; font-size:15px; font-weight:600; }
            QPushButton { background: rgba(239,68,68,0.80); border:none;
                          border-radius:10px; color:#FFFFFF; font-size:13px;
                          font-weight:700; padding:6px 28px; }
            QPushButton:hover { background: rgba(239,68,68,0.95); }
        """)
        dlg.exec()

    def _on_host_disconnected(self):
        from PyQt6.QtWidgets import QMessageBox
        self._sfx.play_disconnect()
        self._disconnect_client()
        self._stack.setCurrentWidget(self.home_screen)
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Disconnected")
        dlg.setText("The host has disconnected.")
        dlg.setInformativeText("You have been returned to the home screen.")
        dlg.setIcon(QMessageBox.Icon.Information)
        dlg.setStyleSheet("""
            QMessageBox { background: #0EA5E9; }
            QMessageBox QLabel { color:#FFFFFF; font-size:14px; font-weight:600; }
            QPushButton { background:#F97316; border:none; border-radius:10px;
                          color:#FFFFFF; font-size:13px; font-weight:700; padding:6px 24px; }
            QPushButton:hover { background:#FB923C; }
        """)
        dlg.exec()

    def _stop_active_timer(self):
        """Stop the timer ring (and panic sound) on whichever game screen is active."""
        for screen in [self._draw_screen, getattr(self, "_write_screen", None)]:
            if screen:
                try:
                    screen._timer_ring.stop()
                except Exception:
                    pass

    def _on_phase_changed(self, payload: dict):
        phase     = payload.get("phase", "")
        prompt    = payload.get("prompt", "")
        image_b64 = payload.get("image", "")
        round_str = payload.get("round_str", "")
        time_secs = payload.get("time_secs", 180)

        self._stop_active_timer()   # ← kill panic sound before switching
        self._sfx.play_music_lobby()

        if phase == "write_sentence":
            # Convert image_b64 to QPixmap if present (guess mode)
            image_px = None
            if image_b64:
                image_px = self._b64_to_pixmap(image_b64)
            self._go_write(round_str=round_str, seconds=max(30, time_secs // 2), image=image_px)

        elif phase == "draw":
            self._set_fullscreen_mode(True)
            self._go_draw(prompt=prompt, round_str=round_str, seconds=time_secs)

    def _on_show_results(self, payload: dict):
        from app.screens.results import ResultsScreen
        chains = payload.get("chains", [])
        self._stop_active_timer()   # ← kill panic sound before results
        self._leave_game_phase()
        self._set_fullscreen_mode(False)

        if hasattr(self, "_results_screen") and self._results_screen:
            self._stack.removeWidget(self._results_screen)
            self._results_screen.deleteLater()

        self._results_screen = ResultsScreen(
            chains,
            is_host=self._is_host,
            letter_secs=self._game_settings.get("result_letter_secs", 0.125),
            drawing_secs=self._game_settings.get("result_drawing_secs", 5.0),
            host_control=self._game_settings.get("host_result_control", False),
        )
        self._results_screen.back_requested.connect(self._go_home)
        self._results_screen.host_next_requested.connect(
            lambda: self._client.host_next() if self._client else None)
        self._stack.addWidget(self._results_screen)
        self._stack.setCurrentWidget(self._results_screen)
        self._sfx.play_music_home()

        # Start the cinematic reveal after Qt has rendered the screen
        QTimer.singleShot(100, self._results_screen.start_reveal)

    def _on_kicked(self, payload: dict):
        """Server kicked this player — show message and go home."""
        from PyQt6.QtWidgets import QMessageBox
        reason = payload.get("reason", "Host kicked you out the lobby")
        self._disconnect_client()
        self._go_home()
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Kicked")
        dlg.setText(reason)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setStyleSheet("""
            QMessageBox { background: #0EA5E9; }
            QMessageBox QLabel { color:#FFFFFF; font-size:15px; font-weight:600; }
            QPushButton { background:rgba(239,68,68,0.80); border:none;
                          border-radius:10px; color:#FFFFFF; font-size:13px;
                          font-weight:700; padding:6px 28px; }
        """)
        dlg.exec()

    def _on_kick_requested(self, player_id: str):
        if self._client:
            self._client.kick_player(player_id)

    def _on_game_error(self, payload: dict):
        """Fatal server error — show dialog and return everyone to home."""
        from PyQt6.QtWidgets import QMessageBox
        reason = payload.get("reason", "An unexpected error occurred.")
        self._stop_active_timer()
        self._leave_game_phase()
        self._set_fullscreen_mode(False)
        self._disconnect_client()
        self._go_home()
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Game Error")
        dlg.setText(reason)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
        dlg.setStyleSheet("""
            QMessageBox { background: #0EA5E9; }
            QMessageBox QLabel { color:#FFFFFF; font-size:15px; font-weight:600; }
            QPushButton { background:rgba(239,68,68,0.80); border:none;
                          border-radius:10px; color:#FFFFFF; font-size:13px;
                          font-weight:700; padding:6px 28px; }
            QPushButton:hover { background:rgba(239,68,68,0.95); }
        """)
        dlg.exec()

    def _on_host_next(self):
        """HOST_NEXT received — advance to next chain on this client."""
        if hasattr(self, "_results_screen") and self._results_screen:
            self._results_screen.force_next()

    def _on_host_decision(self):
        """Host-only: show continue/stop dialog for 'until host stops' mode."""
        from PyQt6.QtWidgets import QMessageBox
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Continue?")
        dlg.setText("Round complete! Keep playing or show results?")
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dlg.button(QMessageBox.StandardButton.Yes).setText("▶  KEEP PLAYING")
        dlg.button(QMessageBox.StandardButton.No).setText("🏁  SHOW RESULTS")
        dlg.setStyleSheet("""
            QMessageBox { background: #0EA5E9; }
            QMessageBox QLabel { color:#FFFFFF; font-size:15px; font-weight:600; }
            QPushButton { background:rgba(0,0,0,0.25); border:2px solid rgba(255,255,255,0.45);
                          border-radius:10px; color:#FFFFFF; font-size:13px;
                          font-weight:700; padding:6px 24px; }
            QPushButton:hover { background:rgba(0,0,0,0.45); }
        """)
        result = dlg.exec()
        if result == QMessageBox.StandardButton.Yes:
            if self._client:
                self._client.host_continue("continue")
        else:
            if self._client:
                self._client.host_continue("stop")

    def _go_write(self, round_str="1/1", seconds=180, image=None):
        from app.screens.write import WriteScreen
        if hasattr(self, "_write_screen") and self._write_screen:
            self._stack.removeWidget(self._write_screen)
            self._write_screen.deleteLater()
        self._write_screen = WriteScreen(
            round_str=round_str, seconds=seconds, image=image,
            panic_mode=self._game_settings.get("panic_mode", True),
            panic_secs=self._game_settings.get("panic_secs", 15),
            submit_once=self._game_settings.get("submit_once", False),
        )
        self._write_screen.submitted.connect(self._on_sentence_submitted)
        self._write_screen.edit_requested.connect(self._on_sentence_edit)
        self._stack.addWidget(self._write_screen)
        self._stack.setCurrentWidget(self._write_screen)
        self._enter_game_phase()
        self._write_screen.start_timer()

    def _on_sentence_edit(self):
        """Player revoked their sentence — send empty to server to un-submit."""
        if self._client:
            self._client.submit_sentence("__revoked__")

    def _on_sentence_submitted(self, text: str):
        if self._client:
            self._client.submit_sentence(text)

    def _on_kick_requested(self, username: str):
        """Host kicked a player — find their player_id and send kick to server."""
        if self._client and self._lobby:
            # Find player_id from the room's player list via the room_joined payload
            for pid, pdata in self._lobby_players.items():
                if pdata.get("username") == username:
                    self._client.kick_player(pid)
                    return

    def _on_start_requested(self, settings: dict = None):
        if self._client:
            self._sfx.play_start()
            self._game_settings = settings or {}
            self._client.start_game(self._game_settings)

    def closeEvent(self, event):
        try:
            self._sfx.stop_music()
        except Exception:
            pass

        # Clean up browser client
        if self._browser_client:
            try: self._browser_client.disconnect()
            except: pass

        # Shut down server (always attempt — loop may be running even if not "host")
        if self._server_loop and self._server_loop.is_running():
            from app.backend.server import shutdown_server, reset_server
            try:
                future = asyncio.run_coroutine_threadsafe(shutdown_server(), self._server_loop)
                future.result(timeout=2.0)
            except Exception:
                pass
            try:
                self._server_loop.call_soon_threadsafe(self._server_loop.stop)
            except Exception:
                pass
            if hasattr(self, "_server_thread") and self._server_thread:
                try:
                    self._server_thread.join(timeout=1.5)
                except Exception:
                    pass
            reset_server()
            self._server_loop   = None
            self._server_thread = None

        self._disconnect_client()
        event.accept()
        import sys; sys.exit(0)

    def _disconnect_client(self):
        if self._client:
            self._client.disconnect()
            self._client = None

    def _b64_to_pixmap(self, b64):
        if not b64:
            return None
        try:
            import base64
            from PyQt6.QtCore import QByteArray
            data = base64.b64decode(b64)
            ba   = QByteArray(data)
            px   = QPixmap()
            px.loadFromData(ba)
            return px if not px.isNull() else None
        except Exception:
            return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())