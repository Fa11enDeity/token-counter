"""Small atomic state store used for fallback turn-delta accounting."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import TokenBreakdown

SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True, slots=True)
class SessionState:
    turn_id: str | None = None
    baseline: TokenBreakdown | None = None
    reported_turn_id: str | None = None


def default_state_dir() -> Path:
    configured = os.environ.get("TOKEN_COUNTER_DATA_DIR") or os.environ.get(
        "PLUGIN_DATA"
    )
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex" / "token-counter"


class StateStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_state_dir()

    def _path(self, session_id: str) -> Path:
        safe_id = SAFE_ID.sub("_", session_id)
        return self.root / "sessions" / f"{safe_id}.json"

    def load(self, session_id: str) -> SessionState:
        path = self._path(session_id)
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return SessionState()
        if not isinstance(value, Mapping):
            return SessionState()
        turn_id = value.get("turn_id")
        reported = value.get("reported_turn_id")
        return SessionState(
            turn_id=turn_id if isinstance(turn_id, str) else None,
            baseline=TokenBreakdown.from_mapping(value.get("baseline")),
            reported_turn_id=reported if isinstance(reported, str) else None,
        )

    def save(self, session_id: str, state: SessionState) -> None:
        path = self._path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": 1,
            "turn_id": state.turn_id,
            "baseline": state.baseline.to_dict() if state.baseline else None,
            "reported_turn_id": state.reported_turn_id,
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
