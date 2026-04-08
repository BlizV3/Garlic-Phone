from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GamePhase(Enum):
    LOBBY          = "lobby"
    WRITE_SENTENCE = "write_sentence"
    DRAW           = "draw"
    RESULTS        = "results"


@dataclass
class Player:
    id: str
    username: str
    avatar: str = ""
    is_host: bool = False
    is_ready: bool = False

    def to_dict(self) -> dict:
        return {
            "id":       self.id,
            "username": self.username,
            "avatar":   self.avatar,
            "is_host":  self.is_host,
            "is_ready": self.is_ready,
        }

    @staticmethod
    def from_dict(data: dict) -> Player:
        return Player(
            id=       data["id"],
            username= data["username"],
            avatar=   data.get("avatar", ""),
            is_host=  data.get("is_host", False),
            is_ready= data.get("is_ready", False),
        )


@dataclass
class ChainEntry:
    """One step in a chain: sentence → drawing → sentence → drawing ..."""
    type: str            # "sentence" | "drawing"
    author_id: str
    author_username: str
    content: str         # text for sentence, base64 PNG for drawing
    author_avatar: str = ""   # base64 avatar PNG

    def to_dict(self) -> dict:
        return {
            "type":            self.type,
            "author_id":       self.author_id,
            "author_username": self.author_username,
            "content":         self.content,
            "author_avatar":   self.author_avatar,
        }

    @staticmethod
    def from_dict(data: dict) -> ChainEntry:
        return ChainEntry(
            type=            data["type"],
            author_id=       data["author_id"],
            author_username= data["author_username"],
            content=         data["content"],
            author_avatar=   data.get("author_avatar", ""),
        )


@dataclass
class Chain:
    owner_id: str                               # player whose chain this is
    entries: list[ChainEntry] = field(default_factory=list)

    def add(self, entry: ChainEntry):
        self.entries.append(entry)

    def to_dict(self) -> dict:
        return {
            "owner_id": self.owner_id,
            "entries":  [e.to_dict() for e in self.entries],
        }

    @staticmethod
    def from_dict(data: dict) -> Chain:
        return Chain(
            owner_id=data.get("owner_id", ""),
            entries=[ChainEntry.from_dict(e) for e in data.get("entries", [])],
        )


@dataclass
class Room:
    code: str
    host_id: str
    players: dict[str, Player] = field(default_factory=dict)
    phase: GamePhase = GamePhase.LOBBY

    # ── Game settings (set when host starts) ──────────────────────────────
    time_secs: int  = 180   # seconds per phase (0 = infinite)
    turns: int      = 3     # total turns (-1 = until host stops)
    flow: str       = "write_draw"  # write_draw | draw_write | draw_only | write_only

    # ── Round tracking ────────────────────────────────────────────────────
    current_turn: int = 0       # 0-indexed turn number
    current_step: int = 0       # step within a turn (write=0, draw=1 or vice-versa)

    # ── Submission tracking ───────────────────────────────────────────────
    submissions: dict[str, str] = field(default_factory=dict)

    # ── Chains ───────────────────────────────────────────────────────────
    chains: dict[str, Chain] = field(default_factory=dict)   # owner_id → Chain

    # ── Flags ─────────────────────────────────────────────────────────────
    test_mode: bool = False
    waiting_for_host: bool = False  # for "until host stops" turn mode

    def add_player(self, player: Player):
        self.players[player.id] = player

    def remove_player(self, player_id: str):
        self.players.pop(player_id, None)

    def all_submitted(self) -> bool:
        return set(self.submissions.keys()) == set(self.players.keys())

    def player_count(self) -> int:
        return len(self.players)

    def player_list(self) -> list[Player]:
        return list(self.players.values())

    def round_str(self) -> str:
        """Human-readable turn counter, e.g. '1/3'."""
        if self.turns == -1:
            return f"{self.current_turn + 1}/?"
        return f"{self.current_turn + 1}/{self.turns}"

    def steps_per_turn(self) -> list[str]:
        """Returns the ordered list of phases within one turn."""
        if self.flow == "write_draw":
            return ["write_sentence", "draw"]
        elif self.flow == "draw_write":
            return ["draw", "write_sentence"]
        elif self.flow == "draw_only":
            return ["draw"]
        elif self.flow == "write_only":
            return ["write_sentence"]
        return ["write_sentence", "draw"]

    def current_phase_name(self) -> str:
        steps = self.steps_per_turn()
        if self.current_step < len(steps):
            return steps[self.current_step]
        return "results"

    def to_dict(self) -> dict:
        return {
            "code":         self.code,
            "host_id":      self.host_id,
            "players":      {pid: p.to_dict() for pid, p in self.players.items()},
            "phase":        self.phase.value,
            "time_secs":    self.time_secs,
            "turns":        self.turns,
            "flow":         self.flow,
            "current_turn": self.current_turn,
            "current_step": self.current_step,
        }