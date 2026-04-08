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
        }

        handler = handlers.get(msg_type)
        if handler:
            try:
                await handler(websocket, payload)
            except Exception as e:
                log.error(f"Exception in handler [{msg_type}]: {e}")
                log.error(traceback.format_exc())
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

        # Generate a unique room code
        for _ in range(20):
            room_code = str(uuid.uuid4())[:6].upper()
            if room_code not in self.rooms:
                break

        room = Room(code=room_code, host_id=player_id)
        room.add_player(host)
        room.test_mode = payload.get("test_mode", False)

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

        player_id = str(uuid.uuid4())[:8]
        player = Player(id=player_id,
                        username=payload.get("username", "Player"),
                        avatar=payload.get("avatar", ""),
                        is_host=False)
        room.add_player(player)
        self.connections[websocket] = (player_id, code)

        await websocket.send(msg.msg_room_joined(room.to_dict(), player_id))
        await self.broadcast(room, msg.msg_player_joined(player.to_dict()), exclude=websocket)
        log.info(f"{player.username} joined room {code} "
                 f"({room.player_count()} players)")

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
        if room.current_step == 0 and room.current_turn == 0:
            return ""
        chain = room.chains.get(player_id)
        if chain and chain.entries:
            return chain.entries[-1].content
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
    async with websockets.serve(_server_instance.handle_connection, HOST, PORT):
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