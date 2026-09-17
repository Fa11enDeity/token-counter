from pathlib import Path

from token_counter.models import TokenBreakdown
from token_counter.state import SessionState, StateStore


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
