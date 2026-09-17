"""Small atomic state store used for fallback turn-delta accounting."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from .models import TokenBreakdown

SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")
DEFAULT_STALE_AFTER_SECONDS = 30 * 24 * 60 * 60


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

    def _lock_path(self, session_id: str) -> Path:
        return self._path(session_id).with_suffix(".lock")

    @contextmanager
    def locked(self, session_id: str) -> Iterator[None]:
        lock_path = self._lock_path(session_id)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            _lock_file(handle)
            try:
                yield
            finally:
                _unlock_file(handle)

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

    def cleanup_stale(
        self,
        *,
        stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
        exclude_session_id: str | None = None,
        now: float | None = None,
    ) -> int:
        sessions = self.root / "sessions"
        cutoff = (time.time() if now is None else now) - stale_after_seconds
        removed = 0
        try:
            paths = tuple(sessions.glob("*.json"))
        except OSError:
            return 0
        excluded = self._path(exclude_session_id) if exclude_session_id else None
        for path in paths:
            if path == excluded:
                continue
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
                lock_path = path.with_suffix(".lock")
                with lock_path.open("a+b") as handle:
                    if not _try_lock_file(handle):
                        continue
                    try:
                        path.unlink(missing_ok=True)
                        removed += 1
                    finally:
                        _unlock_file(handle)
            except OSError:
                continue
        return removed


if os.name == "nt":
    import msvcrt

    def _prepare_windows_lock(handle: BinaryIO) -> None:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)

    def _lock_file(handle: BinaryIO) -> None:
        _prepare_windows_lock(handle)
        msvcrt.locking(  # type: ignore[attr-defined]
            handle.fileno(),
            msvcrt.LK_LOCK,  # type: ignore[attr-defined]
            1,
        )

    def _try_lock_file(handle: BinaryIO) -> bool:
        _prepare_windows_lock(handle)
        try:
            msvcrt.locking(  # type: ignore[attr-defined]
                handle.fileno(),
                msvcrt.LK_NBLCK,  # type: ignore[attr-defined]
                1,
            )
        except OSError:
            return False
        return True

    def _unlock_file(handle: BinaryIO) -> None:
        handle.seek(0)
        msvcrt.locking(  # type: ignore[attr-defined]
            handle.fileno(),
            msvcrt.LK_UNLCK,  # type: ignore[attr-defined]
            1,
        )

else:
    import fcntl

    def _lock_file(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _try_lock_file(handle: BinaryIO) -> bool:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _unlock_file(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
