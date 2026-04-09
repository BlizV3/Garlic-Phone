"""
Garlic Phone — WebSocket Client
Runs on every machine (including the host's).
Connects to the server and exposes simple methods for the UI to call.

Usage (terminal test):
    python -m app.backend.client
"""

import asyncio
import threading
import logging
import websockets

from app.backend import messages as msg

logging.basicConfig(level=logging.INFO, format="[CLIENT] %(message)s")
log = logging.getLogger(__name__)


class GameClient:
    """
    Runs the WebSocket connection on a background thread so it never
    blocks the PyQt6 UI thread.

    The UI calls methods like client.join_room(...) and registers
    callbacks to receive responses:

        client.on(msg.ROOM_JOINED, self.handle_room_joined)
    """

    def __init__(self):
        self._ws = None
        self._loop = None
        self._thread = None
        self._callbacks: dict[str, list] = {}   # msg_type → [fn, fn, ...]
        self.player_id: str | None = None

    # ── Start / stop ──────────────────────────────────────────────────────────

    def connect(self, host: str, port: int = 8765):
        """
        Connect to the server.
        - host can be a full URL like "wss://garlic-phone.onrender.com"
        - or a plain IP/hostname like "192.168.1.5" (uses ws:// + port)
        """
        if host.startswith("wss://") or host.startswith("ws://"):
            uri = host   # already a full URL
        else:
            uri = f"ws://{host}:{port}"

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(uri,),
            daemon=True,
            name="GameClientLoop"
        )
        self._thread.start()
        log.info(f"Connecting to {uri}...")

    def disconnect(self):
        if self._ws and self._loop:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)

    def _run_loop(self, uri: str):
        self._loop.run_until_complete(self._listen(uri))

    async def _listen(self, uri: str):
        try:
            async with websockets.connect(uri) as ws:
                self._ws = ws
                log.info("Connected to server")
                self._fire("connected", {})
                async for raw in ws:
                    self._handle_raw(raw)
        except Exception as e:
            log.error(f"Connection error: {e}")
            self._fire(msg.ERROR, {"reason": str(e)})

    def _handle_raw(self, raw: str):
        try:
            msg_type, payload = msg.parse(raw)
            log.info(f"Received [{msg_type}]")
            self._fire(msg_type, payload)
        except Exception as e:
            log.error(f"Failed to parse message: {e}")

    # ── Callback registration ─────────────────────────────────────────────────

    def on(self, msg_type: str, callback):
        """
        Register a callback for a message type.
        The callback receives the payload dict.

        Example:
            client.on(msg.PLAYER_JOINED, self.on_player_joined)
        """
        self._callbacks.setdefault(msg_type, []).append(callback)

    def off(self, msg_type: str, callback):
        """Unregister a callback."""
        if msg_type in self._callbacks:
            self._callbacks[msg_type] = [
                cb for cb in self._callbacks[msg_type] if cb != callback
            ]

    def _fire(self, msg_type: str, payload: dict):
        for cb in self._callbacks.get(msg_type, []):
            try:
                cb(payload)
            except Exception as e:
                log.error(f"Callback error for [{msg_type}]: {e}")

    # ── Send helpers ──────────────────────────────────────────────────────────

    def _send(self, message: str):
        """Thread-safe send from the UI thread into the async loop."""
        if self._ws and self._loop:
            asyncio.run_coroutine_threadsafe(self._ws.send(message), self._loop)
        else:
            log.warning("Tried to send before connected")

    # ── Public API (called by the UI) ─────────────────────────────────────────

    def create_room(self, username: str, avatar: str = "", test_mode: bool = False,
                    max_players: int = 8, requires_code: bool = False,
                    custom_code: str = ""):
        self._send(msg.msg_create_room(username, avatar, test_mode=test_mode,
                                       max_players=max_players,
                                       requires_code=requires_code,
                                       custom_code=custom_code))

    def request_rooms(self):
        self._send(msg.msg_request_rooms())

    def join_room(self, code: str, username: str, avatar: str = ""):
        self._send(msg.msg_join_room(code, username, avatar))

    def start_game(self, settings: dict = None):
        self._send(msg.msg_start_game(settings or {}))

    def submit_sentence(self, text: str):
        self._send(msg.msg_submit_sentence(text))

    def submit_drawing(self, image_b64: str):
        self._send(msg.msg_submit_drawing(image_b64))

    def submit_drawing_chunked(self, image_b64: str, chunk_size: int = 256 * 1024):
        """Split large drawings into chunks and send them one by one."""
        import uuid as _uuid
        chunk_id = str(_uuid.uuid4())[:8]
        chunks   = [image_b64[i:i+chunk_size] for i in range(0, len(image_b64), chunk_size)]
        total    = len(chunks)
        for i, chunk in enumerate(chunks):
            self._send(msg.msg_drawing_chunk(chunk_id, i, total, chunk))

    def host_continue(self, action: str):
        """action: 'continue' | 'stop'"""
        self._send(msg.msg_host_continue(action))

    def host_next(self):
        """Host skips to next chain in results."""
        self._send(msg.msg_host_next())


# ── Terminal test ──────────────────────────────────────────────────────────────

def main():
    import time

    print("Garlic Phone — Client Test")
    host = input("Server IP (default: 127.0.0.1): ").strip() or "127.0.0.1"

    client = GameClient()
    current_phase = "disconnected"

    def on_connected(_):
        nonlocal current_phase
        current_phase = "connected"
        print("[✓] Connected to server")
        print("Commands: create | join <code>")

    def on_room_created(payload):
        nonlocal current_phase
        current_phase = "lobby"
        print(f"\n[✓] Room created! Code: {payload.get('code')}  Your ID: {payload.get('player_id')}")
        print("Commands: start")

    def on_room_joined(payload):
        nonlocal current_phase
        current_phase = "lobby"
        print(f"\n[✓] Joined room: {payload.get('room', {}).get('code')}  Your ID: {payload.get('player_id')}")
        print("Waiting for host to start...")

    def on_player_joined(payload):
        print(f"[→] Player joined: {payload.get('player', {}).get('username')}")

    def on_player_left(payload):
        print(f"[→] Player left: {payload.get('username')}")

    def on_game_started(_):
        print("\n[→] Game started!")

    def on_phase_changed(payload):
        nonlocal current_phase
        phase = payload.get("phase")
        current_phase = phase
        prompt = payload.get("prompt", "")
        image  = payload.get("image",  "")

        print(f"\n{'─'*40}")
        if phase == "write_sentence":
            print("[PHASE] Write a sentence for someone to draw!")
            print("Command: sentence")
        elif phase == "draw":
            print(f"[PHASE] Draw this: \"{prompt}\"")
            print("Command: drawing  (in real game this will be a canvas)")
        elif phase == "guess":
            print("[PHASE] Guess what was drawn! (image received)")
            print("Command: guess")
        elif phase == "results":
            print("[PHASE] Results!")
        print(f"{'─'*40}")

    def on_ack(_):
        print("[✓] Submission received — waiting for other players...")

    def on_error(payload):
        print(f"[✗] Error: {payload.get('reason')}")

    def on_results(payload):
        print("\n[RESULTS] Game over!")

    def on_return_to_lobby(payload):
        nonlocal current_phase
        current_phase = "lobby"
        print("\n[→] Returning to lobby...")

    client.on("connected",          on_connected)
    client.on(msg.ROOM_CREATED,     on_room_created)
    client.on(msg.ROOM_JOINED,      on_room_joined)
    client.on(msg.PLAYER_JOINED,    on_player_joined)
    client.on(msg.PLAYER_LEFT,      on_player_left)
    client.on(msg.GAME_STARTED,     on_game_started)
    client.on(msg.PHASE_CHANGED,    on_phase_changed)
    client.on(msg.SUBMISSION_ACK,   on_ack)
    client.on(msg.SHOW_RESULTS,     on_results)
    client.on(msg.RETURN_TO_LOBBY,  on_return_to_lobby)
    client.on(msg.ERROR,            on_error)

    client.connect(host)
    time.sleep(0.5)

    username = input("Your username: ").strip() or "TestPlayer"

    while True:
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            client.disconnect()
            break

        if cmd == "quit":
            client.disconnect()
            break
        elif cmd == "create":
            client.create_room(username)
        elif cmd.startswith("join"):
            parts = cmd.split()
            code = parts[1].upper() if len(parts) > 1 else input("Room code: ").strip().upper()
            client.join_room(code, username)
        elif cmd == "start":
            client.start_game()
        elif cmd == "sentence":
            if current_phase != "write_sentence":
                print(f"[!] Can't submit sentence in phase: {current_phase}")
            else:
                text = input("Your sentence: ").strip()
                client.submit_sentence(text)
        elif cmd == "drawing":
            if current_phase != "draw":
                print(f"[!] Can't submit drawing in phase: {current_phase}")
            else:
                # Placeholder — real game will send canvas image
                client.submit_drawing("placeholder_drawing")
        elif cmd == "guess":
            if current_phase != "guess":
                print(f"[!] Can't submit guess in phase: {current_phase}")
            else:
                text = input("Your guess: ").strip()
                client.submit_guess(text)
        else:
            print(f"[!] Unknown command: {cmd}")

        time.sleep(0.2)


if __name__ == "__main__":
    main()