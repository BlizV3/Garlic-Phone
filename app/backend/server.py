import asyncio
import uuid
import logging
import traceback
import websockets
from websockets.server import WebSocketServerProtocol

from app.backend.game_state import Room, Player, Chain, ChainEntry, GamePhase
from app.backend import messages as msg

logging.basicConfig(level=logging.INFO, format="[CLIENT] %(message)s")
log = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = 8765


class GameServer:
    def __init__(self):
        # Multiple rooms: code → Room
        self.rooms: dict[str, Room] = {}
        # Each connection maps to (player_id, room_code)
        self.connections: dict[WebSocketServerProtocol, tuple[str, str]] = {}
        # Chunk buffers: (player_id, chunk_id) → {index: data_str}
        self._chunk_buffers: dict[tuple, dict] = {}

    async def _detect_country(self, websocket) -> str:
        """Detect country from the websocket's remote IP. Returns flag emoji + country name."""
        try:
            ip = websocket.remote_address[0]
            if ip in ("127.0.0.1", "::1") or ip.startswith("10.") or ip.startswith("192.168."):
                return "🏠 Local"
            import urllib.request
            with urllib.request.urlopen(
                f"https://ipapi.co/{ip}/json/", timeout=3
            ) as resp:
                import json
                data = json.loads(resp.read())
                country = data.get("country_name", "")
                # Convert country code to flag emoji
                code = data.get("country_code", "")
                flag = "".join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code.upper()) if len(code) == 2 else ""
                return f"{flag} {country}".strip()
        except Exception:
            return ""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_room(self, websocket) -> Room | None:
        entry = self.connections.get(websocket)
        if not entry:
            return None
        _, room_code = entry
        return self.rooms.get(room_code)

    def _get_player_id(self, websocket) -> str | None:
        entry = self.connections.get(websocket)
        return entry[0] if entry else None

    def _get_player_room(self, websocket) -> tuple[str | None, Room | None]:
        entry = self.connections.get(websocket)
        if not entry:
            return None, None
        player_id, room_code = entry
        return player_id, self.rooms.get(room_code)

    def _websocket_for(self, player_id: str, room: Room):
        for ws, (pid, code) in self.connections.items():
            if pid == player_id and code == room.code:
                return ws
        return None

    async def broadcast(self, room: Room, message: str, exclude=None):
        for ws, (pid, code) in list(self.connections.items()):
            if code != room.code or ws is exclude:
                continue
            try:
                await ws.send(message)
            except websockets.exceptions.ConnectionClosed:
                pass

    def _close_room(self, room: Room):
        """Remove room and all its connections from tracking."""
        code = room.code
        dead = [ws for ws, (_, c) in self.connections.items() if c == code]
        for ws in dead:
            self.connections.pop(ws, None)
        self.rooms.pop(code, None)
        log.info(f"Room {code} closed")

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def handle_connection(self, websocket: WebSocketServerProtocol):
        log.info(f"New connection from {websocket.remote_address}")
        try:
            async for raw in websocket:
                await self.handle_message(websocket, raw)
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except websockets.exceptions.ConnectionClosedError as e:
            log.warning(f"Connection closed with error: {e}")
        except Exception as e:
            log.error(f"Unhandled exception in connection: {e}")
            log.error(traceback.format_exc())
        finally:
            await self.handle_disconnect(websocket)

    async def handle_disconnect(self, websocket: WebSocketServerProtocol):
        player_id, room = self._get_player_room(websocket)
        if not player_id or not room:
            self.connections.pop(websocket, None)
            return

        player = room.players.get(player_id)
        if not player:
            self.connections.pop(websocket, None)
            return

        log.info(f"Player disconnected: {player.username} from room {room.code}")
        self.connections.pop(websocket, None)

        if player_id == room.host_id:
            log.info(f"Host disconnected — closing room {room.code}")
            await self.broadcast(room, msg.msg_host_disconnected())
            # Close all remaining connections in this room
            dead = [ws for ws, (_, c) in list(self.connections.items()) if c == room.code]
            for ws in dead:
                self.connections.pop(ws, None)
                try:
                    await ws.close()
                except Exception:
                    pass
            self.rooms.pop(room.code, None)
        else:
            room.remove_player(player_id)
            await self.broadcast(room, msg.msg_player_left(player_id, player.username))
            # Clean up empty rooms
            if room.player_count() == 0:
                self.rooms.pop(room.code, None)
                log.info(f"Room {room.code} removed (empty)")

    # ── Message routing ────────────────────────────────────────────────────────

    async def handle_message(self, websocket: WebSocketServerProtocol, raw: str):
        try:
            msg_type, payload = msg.parse(raw)
        except Exception:
            await websocket.send(msg.msg_error("Invalid message format"))
            return

        log.info(f"Received [{msg_type}] from {websocket.remote_address}")

        handlers = {
            msg.CREATE_ROOM:     self.on_create_room,
            msg.JOIN_ROOM:       self.on_join_room,
            msg.START_GAME:      self.on_start_game,
            msg.SUBMIT_SENTENCE: self.on_submit_sentence,
            msg.SUBMIT_DRAWING:  self.on_submit_drawing,
            msg.HOST_CONTINUE:   self.on_host_continue,
            msg.HOST_NEXT:       self.on_host_next,
            msg.REQUEST_ROOMS:   self.on_request_rooms,
            msg.DRAWING_CHUNK:   self.on_drawing_chunk,
            msg.KICK_PLAYER:     self.on_kick_player,
        }

        handler = handlers.get(msg_type)
        if handler:
            try:
                await handler(websocket, payload)
            except Exception as e:
                log.error(f"Exception in handler [{msg_type}]: {e}")
                log.error(traceback.format_exc())
                # Find the room and kick everyone back to home
                _, room = self._get_player_room(websocket)
                if room:
                    try:
                        await self.broadcast(room, msg.msg_game_error(
                            f"A server error occurred — everyone has been returned to the home screen."
                        ))
                    except Exception:
                        pass
                    self._close_room(room)
                else:
                    try:
                        await websocket.send(msg.msg_error(f"Server error: {e}"))
                    except Exception:
                        pass
        else:
            await websocket.send(msg.msg_error(f"Unknown message type: {msg_type}"))

    # ── Handlers ───────────────────────────────────────────────────────────────

    async def on_create_room(self, websocket, payload):
        player_id = str(uuid.uuid4())[:8]
        host = Player(id=player_id,
                      username=payload.get("username", "Host"),
                      avatar=payload.get("avatar", ""),
                      is_host=True)

        # Use custom code if provided, otherwise generate one
        custom_code = payload.get("custom_code", "").strip().upper()
        if custom_code and len(custom_code) >= 3:
            if custom_code in self.rooms:
                await websocket.send(msg.msg_error("That room code is already taken — try another"))
                return
            room_code = custom_code
        else:
            for _ in range(20):
                room_code = str(uuid.uuid4())[:6].upper()
                if room_code not in self.rooms:
                    break

        room = Room(code=room_code, host_id=player_id)
        room.add_player(host)
        room.test_mode     = payload.get("test_mode", False)
        room.max_players   = payload.get("max_players", 8)
        room.requires_code = payload.get("requires_code", False)

        # Detect host country from IP (best-effort, no API key needed)
        room.host_country = await self._detect_country(websocket)

        self.rooms[room_code] = room
        self.connections[websocket] = (player_id, room_code)

        await websocket.send(msg.msg_room_created(room_code, player_id))
        log.info(f"Room created: {room_code} by {host.username} "
                 f"({len(self.rooms)} active rooms)")

    async def on_join_room(self, websocket, payload):
        code = payload.get("code", "").upper()

        room = self.rooms.get(code)
        if room is None:
            await websocket.send(msg.msg_error("Room not found — check the code and try again"))
            return
        if room.phase != GamePhase.LOBBY:
            await websocket.send(msg.msg_error("Game already in progress"))
            return

        # Password check
        if getattr(room, "requires_code", False):
            password = payload.get("password", "").strip().upper()
            if password != code:
                await websocket.send(msg.msg_error("Wrong password — try again"))
                return

        # Duplicate username check
        username = payload.get("username", "Player").strip()
        existing_names = {p.username.lower() for p in room.players.values()}
        if username.lower() in existing_names:
            await websocket.send(msg.msg_error(f'Username "{username}" is already taken in this room — please choose another'))
            return

        player_id = str(uuid.uuid4())[:8]
        player = Player(id=player_id, username=username,
                        avatar=payload.get("avatar", ""), is_host=False)
        room.add_player(player)
        self.connections[websocket] = (player_id, code)

        await websocket.send(msg.msg_room_joined(room.to_dict(), player_id))
        await self.broadcast(room, msg.msg_player_joined(player.to_dict()), exclude=websocket)
        log.info(f"{player.username} joined room {code} ({room.player_count()} players)")

    async def on_start_game(self, websocket, payload):
        player_id, room = self._get_player_room(websocket)
        if not room or player_id != room.host_id:
            await websocket.send(msg.msg_error("Only the host can start the game"))
            return
        if room.player_count() < 2 and not getattr(room, "test_mode", False):
            await websocket.send(msg.msg_error("Need at least 2 players to start"))
            return

        settings = payload.get("settings", {})
        room.time_secs    = settings.get("time_secs", 180)
        room.turns        = settings.get("turns", 3)
        room.flow         = settings.get("flow", "write_draw")
        room.current_turn = 0
        room.current_step = 0
        room.submissions  = {}
        room.chains       = {p.id: Chain(owner_id=p.id) for p in room.player_list()}

        await self.broadcast(room, msg.msg_game_started())
        log.info(f"Room {room.code} game started — "
                 f"flow={room.flow} turns={room.turns} time={room.time_secs}s")
        await self._broadcast_current_phase(room)

    async def on_submit_sentence(self, websocket, payload):
        player_id, room = self._get_player_room(websocket)
        if not player_id or not room:
            return
        if room.phase != GamePhase.WRITE_SENTENCE:
            await websocket.send(msg.msg_error("Not in writing phase"))
            return

        text   = payload.get("text", "").strip()
        player = room.players[player_id]

        if text == "__revoked__":
            room.submissions.pop(player_id, None)
            n_sub = len(room.submissions)
            n_tot = room.player_count()
            await self.broadcast(room, msg.msg_submission_ack(n_sub, n_tot))
            log.info(f"{player.username} revoked sentence in {room.code}")
            return

        if not text:
            await websocket.send(msg.msg_error("Sentence cannot be empty"))
            return

        was = player_id in room.submissions
        room.submissions[player_id] = text
        n_sub = len(room.submissions)
        n_tot = room.player_count()
        await self.broadcast(room, msg.msg_submission_ack(n_sub, n_tot))
        log.info(f"{player.username} {'re-submitted' if was else 'submitted'} "
                 f"sentence in {room.code} ({n_sub}/{n_tot})")
        if room.all_submitted():
            await self._advance_step(room)

    async def on_submit_drawing(self, websocket, payload):
        player_id, room = self._get_player_room(websocket)
        if not player_id or not room:
            return
        if room.phase != GamePhase.DRAW:
            await websocket.send(msg.msg_error("Not in drawing phase"))
            return

        image  = payload.get("image", "")
        player = room.players[player_id]

        if image == "__revoked__":
            room.submissions.pop(player_id, None)
            n_sub = len(room.submissions)
            n_tot = room.player_count()
            await self.broadcast(room, msg.msg_submission_ack(n_sub, n_tot))
            log.info(f"{player.username} revoked drawing in {room.code} ({n_sub}/{n_tot})")
            return

        was = player_id in room.submissions
        room.submissions[player_id] = image
        n_sub = len(room.submissions)
        n_tot = room.player_count()
        await self.broadcast(room, msg.msg_submission_ack(n_sub, n_tot))
        log.info(f"{player.username} {'re-submitted' if was else 'submitted'} "
                 f"drawing in {room.code} ({n_sub}/{n_tot})")
        if room.all_submitted():
            await self._advance_step(room)

    async def on_drawing_chunk(self, websocket, payload):
        """Receive one chunk of a drawing, assemble, then process when complete."""
        player_id, room = self._get_player_room(websocket)
        if not player_id or not room:
            return

        chunk_id = payload.get("chunk_id", "")
        index    = payload.get("index", 0)
        total    = payload.get("total", 1)
        data     = payload.get("data", "")

        key = (player_id, chunk_id)
        if key not in self._chunk_buffers:
            self._chunk_buffers[key] = {}
        self._chunk_buffers[key][index] = data

        log.info(f"Chunk {index+1}/{total} from {player_id} in room {room.code}")

        if len(self._chunk_buffers[key]) == total:
            # All chunks received — reassemble in order
            full_image = "".join(
                self._chunk_buffers[key][i] for i in range(total)
            )
            del self._chunk_buffers[key]
            log.info(f"Drawing reassembled ({len(full_image)} chars) from {player_id}")

            # Process exactly like a normal drawing submission
            fake_payload = {"image": full_image}
            await self.on_submit_drawing(websocket, fake_payload)

    async def on_kick_player(self, websocket, payload):
        player_id, room = self._get_player_room(websocket)
        if not room or player_id != room.host_id:
            return
        target_id = payload.get("player_id", "")
        if not target_id or target_id == room.host_id:
            return
        target_ws = self._websocket_for(target_id, room)
        if target_ws:
            await target_ws.send(msg.msg_kicked())
            await target_ws.close()
        # Remove from room
        kicked = room.players.get(target_id)
        if kicked:
            room.remove_player(target_id)
            self.connections.pop(target_ws, None)
            await self.broadcast(room, msg.msg_player_left(target_id, kicked.username))
            log.info(f"Host kicked {kicked.username} from room {room.code}")

    async def on_host_continue(self, websocket, payload):
        player_id, room = self._get_player_room(websocket)
        if not room or player_id != room.host_id:
            return
        action = payload.get("action", "stop")
        if action == "continue":
            room.current_turn += 1
            room.current_step  = 0
            room.submissions   = {}
            await self._broadcast_current_phase(room)
        else:
            await self._show_results(room)

    async def on_request_rooms(self, websocket, payload):
        """Send the client a list of all open lobby rooms. Safe for unregistered connections."""
        try:
            rooms_data = []
            for code, room in list(self.rooms.items()):
                try:
                    if room.phase != GamePhase.LOBBY:
                        continue
                    host = room.players.get(room.host_id)
                    rooms_data.append({
                        "code":          code,
                        "host_username": host.username if host else "?",
                        "host_avatar":   host.avatar   if host else "",
                        "player_count":  room.player_count(),
                        "max_players":   getattr(room, "max_players", 8),
                        "requires_code": getattr(room, "requires_code", False),
                        "country":       getattr(room, "host_country", ""),
                    })
                except Exception as re:
                    log.warning(f"Skipped room {code} in listing: {re}")
            await websocket.send(msg.msg_room_list(rooms_data))
            log.info(f"Sent room list ({len(rooms_data)} open rooms) to {websocket.remote_address}")
        except Exception as e:
            log.error(f"on_request_rooms failed: {e}")
            log.error(traceback.format_exc())

    async def on_host_next(self, websocket, payload):
        player_id, room = self._get_player_room(websocket)
        if not room or player_id != room.host_id:
            return
        await self.broadcast(room, msg.msg_host_next())
        log.info(f"Host skipped to next chain in room {room.code}")

    # ── Phase engine ───────────────────────────────────────────────────────────

    async def _advance_step(self, room: Room):
        steps    = room.steps_per_turn()
        step     = room.current_step
        await self._record_submissions(room)
        next_step = step + 1

        if next_step < len(steps):
            room.current_step = next_step
            room.submissions  = {}
            await self._broadcast_current_phase(room)
        else:
            if room.turns == -1:
                room.waiting_for_host = True
                room.submissions      = {}
                await self._notify_host_continue(room)
            elif room.current_turn + 1 < room.turns:
                room.current_turn += 1
                room.current_step  = 0
                room.submissions   = {}
                await self._broadcast_current_phase(room)
            else:
                await self._show_results(room)

    async def _broadcast_current_phase(self, room: Room):
        phase_name = room.current_phase_name()
        players    = room.player_list()
        secs       = room.time_secs
        round_str  = room.round_str()

        if phase_name == "write_sentence":
            room.phase = GamePhase.WRITE_SENTENCE
            write_secs = max(30, room.time_secs // 2)
            for player in players:
                ws = self._websocket_for(player.id, room)
                if ws:
                    content  = self._get_prompt_for(room, player.id)
                    is_image = len(content) > 500
                    await ws.send(msg.msg_phase_changed(
                        phase_name,
                        prompt="" if is_image else content,
                        image=content if is_image else "",
                        round_str=round_str, time_secs=write_secs))
            log.info(f"Room {room.code} → WRITE (turn {room.current_turn+1}, {write_secs}s)")

        elif phase_name == "draw":
            room.phase = GamePhase.DRAW
            for player in players:
                ws = self._websocket_for(player.id, room)
                if ws:
                    content = self._get_prompt_for(room, player.id)
                    await ws.send(msg.msg_phase_changed(
                        phase_name, prompt=content, image="",
                        round_str=round_str, time_secs=secs))
            log.info(f"Room {room.code} → DRAW (turn {room.current_turn+1})")

    def _get_prompt_for(self, room: Room, player_id: str) -> str:
        """
        Get the content this player needs to respond to.
        Always comes from the chain that was most recently rotated TO this player —
        i.e. the last entry in this player's chain (put there by _record_submissions).
        On first step of first turn there's nothing yet, return empty.
        """
        if room.current_step == 0 and room.current_turn == 0:
            return ""

        players     = room.player_list()
        n           = len(players)
        step        = room.current_step
        turn        = room.current_turn
        steps_per   = len(room.steps_per_turn())
        total_steps = (turn * steps_per) + step

        # Find which origin chain this player is currently holding
        idx         = next((i for i, p in enumerate(players) if p.id == player_id), 0)
        origin_idx  = (idx - total_steps) % n
        origin_player = players[origin_idx]

        # Safety: never give a player their own first entry back
        chain = room.chains.get(origin_player.id)
        if chain and chain.entries:
            # Make sure we're not giving them their own content
            last = chain.entries[-1]
            if last.author_id == player_id and n > 1:
                # Fallback — try the one before
                if len(chain.entries) > 1:
                    return chain.entries[-2].content
                return ""
            return last.content
        return ""

    async def _record_submissions(self, room: Room):
        players    = room.player_list()
        n          = len(players)
        phase_name = room.current_phase_name()
        entry_type = "sentence" if phase_name == "write_sentence" else "drawing"
        step       = room.current_step
        turn       = room.current_turn

        if step == 0 and turn == 0:
            for player in players:
                content = room.submissions.get(player.id, "")
                chain   = room.chains.get(player.id)
                if chain is not None:
                    chain.add(ChainEntry(
                        type=entry_type,
                        author_id=player.id,
                        author_username=player.username,
                        content=content,
                        author_avatar=player.avatar,
                    ))
        else:
            steps_per   = len(room.steps_per_turn())
            total_steps = (turn * steps_per) + step
            for i, player in enumerate(players):
                content = room.submissions.get(player.id, "")
                if not content or content == "__revoked__":
                    continue
                origin_idx    = (i - total_steps) % n
                origin_player = players[origin_idx]
                chain = room.chains.get(origin_player.id)
                if chain is not None:
                    chain.add(ChainEntry(
                        type=entry_type,
                        author_id=player.id,
                        author_username=player.username,
                        content=content,
                        author_avatar=player.avatar,
                    ))

    async def _notify_host_continue(self, room: Room):
        ws = self._websocket_for(room.host_id, room)
        if ws:
            await ws.send(msg.msg_host_decision())
        await self.broadcast(room, msg.msg_waiting_for_host(), exclude=ws)
        log.info(f"Room {room.code} waiting for host to continue or stop")

    async def _show_results(self, room: Room):
        room.phase = GamePhase.RESULTS
        players    = {p.id: p for p in room.player_list()}
        chains     = []
        for c in room.chains.values():
            d = c.to_dict()
            owner = players.get(c.owner_id)
            d["owner_username"] = owner.username if owner else "?"
            d["owner_avatar"]   = owner.avatar   if owner else ""
            chains.append(d)
        await self.broadcast(room, msg.msg_show_results(chains))
        log.info(f"Room {room.code} → RESULTS")
        # Clean up room after results sent (keep connections for a bit)
        # Players will disconnect naturally when they leave


# ── Entry point ────────────────────────────────────────────────────────────────

_server_instance: GameServer = None


async def start_server():
    global _server_instance
    _server_instance = GameServer()
    log.info(f"Starting server on {HOST}:{PORT}")
    async with websockets.serve(
        _server_instance.handle_connection, HOST, PORT,
        max_size=10 * 1024 * 1024,   # 10 MB — plenty for any drawing
    ):
        log.info(f"server listening on {HOST}:{PORT}")
        log.info(f"Server is running. Share your local IP + port {PORT} with players.")
        await asyncio.Future()


async def shutdown_server():
    global _server_instance
    if _server_instance is None:
        return
    server = _server_instance
    try:
        for room in list(server.rooms.values()):
            await server.broadcast(room, msg.msg_host_disconnected())
    except Exception:
        pass
    await asyncio.sleep(0.3)
    for ws in list(server.connections.keys()):
        try:
            await ws.close()
        except Exception:
            pass
    server.connections.clear()
    server.rooms.clear()
    _server_instance = None


def reset_server():
    global _server_instance
    _server_instance = None


if __name__ == "__main__":
    asyncio.run(start_server())