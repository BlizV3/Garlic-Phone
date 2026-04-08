import asyncio
import uuid
import logging
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
        self.room: Room | None = None
        self.connections: dict[WebSocketServerProtocol, str] = {}

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
            import traceback
            log.error(f"Unhandled exception in connection: {e}")
            log.error(traceback.format_exc())
        finally:
            await self.handle_disconnect(websocket)

    async def handle_disconnect(self, websocket: WebSocketServerProtocol):
        player_id = self.connections.pop(websocket, None)
        if not player_id or not self.room or player_id not in self.room.players:
            return
        player = self.room.players[player_id]
        log.info(f"Player disconnected: {player.username}")
        if player_id == self.room.host_id:
            log.info("Host disconnected — kicking all players")
            await self.broadcast(msg.msg_host_disconnected())
            for ws in list(self.connections.keys()):
                try:
                    await ws.close()
                except Exception:
                    pass
            self.connections.clear()
            self.room = None
        else:
            self.room.remove_player(player_id)
            await self.broadcast(msg.msg_player_left(player_id, player.username))

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
                import traceback
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
        if self.room is not None:
            await websocket.send(msg.msg_error("A room already exists on this server"))
            return
        player_id = str(uuid.uuid4())[:8]
        host = Player(id=player_id, username=payload.get("username", "Host"),
                      avatar=payload.get("avatar", ""), is_host=True)
        room_code = str(uuid.uuid4())[:6].upper()
        self.room = Room(code=room_code, host_id=player_id)
        self.room.add_player(host)
        self.room.test_mode = payload.get("test_mode", False)
        self.connections[websocket] = player_id
        await websocket.send(msg.msg_room_created(room_code, player_id))
        log.info(f"Room created: {room_code} by {host.username}")

    async def on_join_room(self, websocket, payload):
        code = payload.get("code", "").upper()
        if self.room is None:
            await websocket.send(msg.msg_error("No room exists on this server"))
            return
        if self.room.code != code:
            await websocket.send(msg.msg_error("Wrong room code"))
            return
        if self.room.phase != GamePhase.LOBBY:
            await websocket.send(msg.msg_error("Game already in progress"))
            return
        player_id = str(uuid.uuid4())[:8]
        player = Player(id=player_id, username=payload.get("username", "Player"),
                        avatar=payload.get("avatar", ""), is_host=False)
        self.room.add_player(player)
        self.connections[websocket] = player_id
        await websocket.send(msg.msg_room_joined(self.room.to_dict(), player_id))
        await self.broadcast(msg.msg_player_joined(player.to_dict()), exclude=websocket)
        log.info(f"{player.username} joined room {code}")

    async def on_start_game(self, websocket, payload):
        player_id = self.connections.get(websocket)
        if not self.room or player_id != self.room.host_id:
            await websocket.send(msg.msg_error("Only the host can start the game"))
            return
        if self.room.player_count() < 2 and not self.room.test_mode:
            await websocket.send(msg.msg_error("Need at least 2 players to start"))
            return

        # Apply settings from payload
        settings = payload.get("settings", {})
        self.room.time_secs    = settings.get("time_secs", 180)
        self.room.turns        = settings.get("turns", 3)
        self.room.flow         = settings.get("flow", "write_draw")
        self.room.current_turn = 0
        self.room.current_step = 0
        self.room.submissions  = {}
        self.room.chains       = {p.id: Chain(owner_id=p.id)
                                  for p in self.room.player_list()}

        await self.broadcast(msg.msg_game_started())
        log.info(f"Game started — flow={self.room.flow} turns={self.room.turns} "
                 f"time={self.room.time_secs}s")
        await self._broadcast_current_phase()

    async def on_submit_sentence(self, websocket, payload):
        player_id = self._player_id(websocket)
        if not player_id or not self.room:
            return
        if self.room.phase != GamePhase.WRITE_SENTENCE:
            await websocket.send(msg.msg_error("Not in writing phase"))
            return
        text = payload.get("text", "").strip()
        if not text:
            await websocket.send(msg.msg_error("Sentence cannot be empty"))
            return
        player = self.room.players[player_id]
        was_submitted = player_id in self.room.submissions
        self.room.submissions[player_id] = text

        # __revoked__ means the player hit Edit — remove their submission
        if text == "__revoked__":
            self.room.submissions.pop(player_id, None)
            n_sub = len(self.room.submissions)
            n_tot = self.room.player_count()
            await self.broadcast(msg.msg_submission_ack(n_sub, n_tot))
            log.info(f"{player.username} revoked sentence ({n_sub}/{n_tot})")
            return

        n_sub = len(self.room.submissions)
        n_tot = self.room.player_count()
        await self.broadcast(msg.msg_submission_ack(n_sub, n_tot))
        log.info(f"{player.username} {'re-submitted' if was_submitted else 'submitted'} sentence "
                 f"({n_sub}/{n_tot})")
        if self.room.all_submitted():
            await self._advance_step()

    async def on_submit_drawing(self, websocket, payload):
        player_id = self._player_id(websocket)
        if not player_id or not self.room:
            return
        if self.room.phase != GamePhase.DRAW:
            await websocket.send(msg.msg_error("Not in drawing phase"))
            return
        image = payload.get("image", "")
        player = self.room.players[player_id]
        was_submitted = player_id in self.room.submissions

        # __revoked__ means the player hit Edit — remove their submission
        if image == "__revoked__":
            self.room.submissions.pop(player_id, None)
            n_sub = len(self.room.submissions)
            n_tot = self.room.player_count()
            await self.broadcast(msg.msg_submission_ack(n_sub, n_tot))
            log.info(f"{player.username} revoked drawing ({n_sub}/{n_tot})")
            return

        self.room.submissions[player_id] = image
        n_sub = len(self.room.submissions)
        n_tot = self.room.player_count()
        await self.broadcast(msg.msg_submission_ack(n_sub, n_tot))
        log.info(f"{player.username} {'re-submitted' if was_submitted else 'submitted'} drawing "
                 f"({len(self.room.submissions)}/{self.room.player_count()})")
        if self.room.all_submitted():
            await self._advance_step()

    async def on_host_next(self, websocket, payload):
        """Host pressed Next in results — broadcast to all clients."""
        player_id = self.connections.get(websocket)
        if not self.room or player_id != self.room.host_id:
            return
        await self.broadcast(msg.msg_host_next())
        log.info("Host skipped to next chain")

    async def on_host_continue(self, websocket, payload):
        """Host presses continue or stop when turns = 'until host stops'."""
        player_id = self.connections.get(websocket)
        if not self.room or player_id != self.room.host_id:
            return
        action = payload.get("action", "stop")
        if action == "continue":
            self.room.current_turn += 1
            self.room.current_step  = 0
            self.room.submissions   = {}
            await self._broadcast_current_phase()
        else:
            await self._show_results()
        """Host presses continue or stop when turns = 'until host stops'."""
        player_id = self.connections.get(websocket)
        if not self.room or player_id != self.room.host_id:
            return
        action = payload.get("action", "stop")   # "continue" | "stop"
        if action == "continue":
            self.room.current_turn += 1
            self.room.current_step  = 0
            self.room.submissions   = {}
            await self._broadcast_current_phase()
        else:
            await self._show_results()

    # ── Phase engine ───────────────────────────────────────────────────────────

    async def _advance_step(self):
        """Called when all players have submitted. Move to the next step or turn."""
        steps = self.room.steps_per_turn()
        step  = self.room.current_step

        # Record this step's submissions into chains (rotated)
        await self._record_submissions()

        next_step = step + 1

        if next_step < len(steps):
            # Still more steps in this turn
            self.room.current_step = next_step
            self.room.submissions  = {}
            await self._broadcast_current_phase()
        else:
            # Turn complete
            if self.room.turns == -1:
                # "Until host stops" — tell host to decide
                self.room.waiting_for_host = True
                self.room.submissions      = {}
                await self._notify_host_continue()
            elif self.room.current_turn + 1 < self.room.turns:
                # More turns remaining
                self.room.current_turn += 1
                self.room.current_step  = 0
                self.room.submissions   = {}
                await self._broadcast_current_phase()
            else:
                # All turns done
                await self._show_results()

    async def _broadcast_current_phase(self):
        """Send each player the correct phase + their personal prompt/image."""
        phase_name = self.room.current_phase_name()
        players    = self.room.player_list()
        secs       = self.room.time_secs
        round_str  = self.room.round_str()
        is_first   = (self.room.current_step == 0 and self.room.current_turn == 0)

        if phase_name == "write_sentence":
            self.room.phase = GamePhase.WRITE_SENTENCE
            write_secs = max(30, self.room.time_secs // 2)  # half the draw time
            for player in players:
                ws = self._websocket_for(player.id)
                if ws:
                    content = self._get_prompt_for(player.id, phase_name)
                    is_image = len(content) > 500
                    await ws.send(msg.msg_phase_changed(
                        phase_name,
                        prompt="" if is_image else content,
                        image=content if is_image else "",
                        round_str=round_str, time_secs=write_secs))
            log.info(f"Phase → WRITE  (turn {self.room.current_turn+1}, {write_secs}s)")

        elif phase_name == "draw":
            self.room.phase = GamePhase.DRAW
            for player in players:
                ws = self._websocket_for(player.id)
                if ws:
                    content = self._get_prompt_for(player.id, phase_name)
                    # Prompt is always text for draw phase (sentence to draw)
                    await ws.send(msg.msg_phase_changed(
                        phase_name,
                        prompt=content,
                        image="",
                        round_str=round_str, time_secs=secs))
            log.info(f"Phase → DRAW  (turn {self.room.current_turn+1})")

    def _get_prompt_for(self, player_id: str, phase_name: str) -> str:
        """Get the prompt/image this player should receive for the current phase."""
        # First step of first turn — no prompt yet, player invents their own
        if self.room.current_step == 0 and self.room.current_turn == 0:
            return ""

        # After first step, the player's own chain holds what they need to respond to
        chain = self.room.chains.get(player_id)
        if chain and chain.entries:
            return chain.entries[-1].content

        return ""

    async def _record_submissions(self):
        """
        Build chains that follow the content as it rotates.
        Each player starts a chain with their own submission.
        On subsequent steps the rotated content is appended to the chain
        that *started* with that content thread.
        """
        players    = self.room.player_list()
        n          = len(players)
        phase_name = self.room.current_phase_name()
        entry_type = "sentence" if phase_name == "write_sentence" else "drawing"
        step       = self.room.current_step
        turn       = self.room.current_turn

        if step == 0 and turn == 0:
            # First step — each player starts their own chain
            for player in players:
                content = self.room.submissions.get(player.id, "")
                chain   = self.room.chains.get(player.id)
                if chain is not None:
                    chain.add(ChainEntry(
                        type=entry_type,
                        author_id=player.id,
                        author_username=player.username,
                        content=content,
                        author_avatar=player.avatar,
                    ))
        else:
            # Subsequent steps — each player worked on rotated content.
            # Total rotation = how many steps have elapsed across all turns.
            steps_per = len(self.room.steps_per_turn())
            total_steps = (turn * steps_per) + step
            for i, player in enumerate(players):
                content = self.room.submissions.get(player.id, "")
                if not content or content == "__revoked__":
                    continue
                origin_idx    = (i - total_steps) % n
                origin_player = players[origin_idx]
                chain = self.room.chains.get(origin_player.id)
                if chain is not None:
                    chain.add(ChainEntry(
                        type=entry_type,
                        author_id=player.id,
                        author_username=player.username,
                        content=content,
                        author_avatar=player.avatar,
                    ))

    async def _notify_host_continue(self):
        """Tell the host to decide whether to continue or stop."""
        ws = self._websocket_for(self.room.host_id)
        if ws:
            await ws.send(msg.msg_host_decision())
        # Tell all other players to wait
        await self.broadcast(msg.msg_waiting_for_host(), exclude=ws)
        log.info("Waiting for host to continue or stop")

    async def _show_results(self):
        self.room.phase = GamePhase.RESULTS
        players = {p.id: p for p in self.room.player_list()}
        chains  = []
        for c in self.room.chains.values():
            d = c.to_dict()
            owner = players.get(c.owner_id)
            d["owner_username"] = owner.username if owner else "?"
            d["owner_avatar"]   = owner.avatar   if owner else ""
            chains.append(d)
        await self.broadcast(msg.msg_show_results(chains))
        log.info("Phase → RESULTS")

    # ── Utilities ──────────────────────────────────────────────────────────────

    async def broadcast(self, message: str, exclude=None):
        for ws in list(self.connections.keys()):
            if ws is exclude:
                continue
            try:
                await ws.send(message)
            except websockets.exceptions.ConnectionClosed:
                pass

    def _player_id(self, websocket) -> str | None:
        return self.connections.get(websocket)

    def _websocket_for(self, player_id: str):
        for ws, pid in self.connections.items():
            if pid == player_id:
                return ws
        return None


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
    if server.connections:
        try:
            await server.broadcast(msg.msg_host_disconnected())
        except Exception:
            pass
        await asyncio.sleep(0.3)
        for ws in list(server.connections.keys()):
            try:
                await ws.close()
            except Exception:
                pass
    server.connections.clear()
    server.room = None
    _server_instance = None


def reset_server():
    """Synchronously wipe the global server instance so a fresh one can start."""
    global _server_instance
    _server_instance = None


if __name__ == "__main__":
    asyncio.run(start_server())