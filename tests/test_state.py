import os
from pathlib import Path

from token_counter.models import TokenBreakdown
from token_counter.state import SessionState, StateStore, default_state_dir


def test_default_state_dir_prefers_explicit_configuration(
    tmp_path: Path, monkeypatch: object
) -> None:
    configured = tmp_path / "configured"
    plugin_data = tmp_path / "plugin"
    monkeypatch.setenv("PLUGIN_DATA", str(plugin_data))  # type: ignore[attr-defined]
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "TOKEN_COUNTER_DATA_DIR", str(configured)
    )

    assert default_state_dir() == configured


def test_state_round_trip_and_session_filename_sanitizing(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    expected = SessionState(
        turn_id="turn-1",
        baseline=TokenBreakdown(input_tokens=10, total_tokens=12),
        reported_turn_id="turn-0",
    )
    store.save("session/with spaces", expected)

    assert store.load("session/with spaces") == expected
    assert (tmp_path / "sessions" / "session_with_spaces.json").is_file()


def test_corrupt_state_is_treated_as_empty(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    state_path = tmp_path / "sessions" / "session.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("not json", encoding="utf-8")

    assert store.load("session") == SessionState()

    state_path.write_text("[]", encoding="utf-8")
    assert store.load("session") == SessionState()


def test_cleanup_stale_removes_only_expired_inactive_state(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save("stale", SessionState(turn_id="old"))
    store.save("active", SessionState(turn_id="current"))
    store.save("fresh", SessionState(turn_id="new"))
    stale_path = tmp_path / "sessions" / "stale.json"
    active_path = tmp_path / "sessions" / "active.json"
    old_time = 100.0
    os.utime(stale_path, (old_time, old_time))
    os.utime(active_path, (old_time, old_time))

    removed = store.cleanup_stale(
        stale_after_seconds=50,
        exclude_session_id="active",
        now=200.0,
    )

    assert removed == 1
    assert not stale_path.exists()
    assert active_path.exists()
    assert (tmp_path / "sessions" / "fresh.json").exists()


def test_locked_state_round_trip(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    with store.locked("session"):
        store.save("session", SessionState(turn_id="turn-1"))
    assert store.load("session").turn_id == "turn-1"


def test_cleanup_skips_a_locked_stale_session(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save("locked", SessionState(turn_id="turn-1"))
    state_path = tmp_path / "sessions" / "locked.json"
    os.utime(state_path, (100.0, 100.0))

    with store.locked("locked"):
        assert store.cleanup_stale(stale_after_seconds=50, now=200.0) == 0

    assert state_path.exists()
