import json

# ── Client → Server ────────────────────────────────────────────────────────────
JOIN_ROOM        = "join_room"
CREATE_ROOM      = "create_room"
START_GAME       = "start_game"
SUBMIT_SENTENCE  = "submit_sentence"
SUBMIT_DRAWING   = "submit_drawing"
HOST_CONTINUE    = "host_continue"    # host decides continue/stop in endless mode
HOST_NEXT        = "host_next"        # host skips to next chain in results

# ── Server → Client ────────────────────────────────────────────────────────────
ROOM_CREATED      = "room_created"
ROOM_JOINED       = "room_joined"
PLAYER_JOINED     = "player_joined"
PLAYER_LEFT       = "player_left"
GAME_STARTED      = "game_started"
PHASE_CHANGED     = "phase_changed"
SUBMISSION_ACK    = "submission_ack"
SHOW_RESULTS      = "show_results"
RETURN_TO_LOBBY   = "return_to_lobby"
HOST_DECISION     = "host_decision"    # sent to host: continue or stop?
WAITING_FOR_HOST  = "waiting_for_host" # sent to players: host is deciding
ERROR             = "error"
HOST_DISCONNECTED = "host_disconnected"


def build(msg_type: str, **payload) -> str:
    return json.dumps({"type": msg_type, "payload": payload})

def parse(raw: str) -> tuple[str, dict]:
    data = json.loads(raw)
    return data["type"], data.get("payload", {})


# ── Client → Server builders ───────────────────────────────────────────────────

def msg_create_room(username: str, avatar: str = "", test_mode: bool = False) -> str:
    return build(CREATE_ROOM, username=username, avatar=avatar, test_mode=test_mode)

def msg_join_room(code: str, username: str, avatar: str = "") -> str:
    return build(JOIN_ROOM, code=code, username=username, avatar=avatar)

def msg_start_game(settings: dict = None) -> str:
    return build(START_GAME, settings=settings or {})

def msg_submit_sentence(text: str) -> str:
    return build(SUBMIT_SENTENCE, text=text)

def msg_submit_drawing(image_b64: str) -> str:
    return build(SUBMIT_DRAWING, image=image_b64)

def msg_host_continue(action: str) -> str:
    """action: 'continue' | 'stop'"""
    return build(HOST_CONTINUE, action=action)

def msg_host_next() -> str:
    """Broadcast from server: skip to next chain in results."""
    return build(HOST_NEXT)


# ── Server → Client builders ───────────────────────────────────────────────────

def msg_room_created(code: str, player_id: str) -> str:
    return build(ROOM_CREATED, code=code, player_id=player_id)

def msg_room_joined(room: dict, player_id: str) -> str:
    return build(ROOM_JOINED, room=room, player_id=player_id)

def msg_player_joined(player: dict) -> str:
    return build(PLAYER_JOINED, player=player)

def msg_player_left(player_id: str, username: str) -> str:
    return build(PLAYER_LEFT, player_id=player_id, username=username)

def msg_game_started() -> str:
    return build(GAME_STARTED)

def msg_phase_changed(phase: str, prompt: str = "", image: str = "",
                      round_str: str = "", time_secs: int = 180) -> str:
    return build(PHASE_CHANGED, phase=phase, prompt=prompt,
                 image=image, round_str=round_str, time_secs=time_secs)

def msg_submission_ack(submitted: int = 0, total: int = 0) -> str:
    return build(SUBMISSION_ACK, submitted=submitted, total=total)

def msg_show_results(chains: list) -> str:
    return build(SHOW_RESULTS, chains=chains)

def msg_return_to_lobby(room: dict) -> str:
    return build(RETURN_TO_LOBBY, room=room)

def msg_host_decision() -> str:
    return build(HOST_DECISION)

def msg_waiting_for_host() -> str:
    return build(WAITING_FOR_HOST)

def msg_error(reason: str) -> str:
    return build(ERROR, reason=reason)

def msg_host_disconnected() -> str:
    return build(HOST_DISCONNECTED)