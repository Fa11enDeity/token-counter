import json
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path

from token_counter.cli import main
from token_counter.models import TokenBreakdown
from token_counter.state import SessionState, StateStore


def test_invalid_input_does_not_fail_hook() -> None:
    stdout = StringIO()
    assert main(StringIO("not-json"), stdout) == 0
    assert stdout.getvalue() == ""


def test_stop_hook_emits_json(tmp_path: Path, monkeypatch: object) -> None:
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "turn_context",
                        "payload": {
                            "turn_id": "turn-1",
                            "model": "gpt-5.6-sol",
                            "effort": "medium",
                            "service_tier": None,
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "token_usage_record",
                        "payload": {
                            "turn_id": "turn-1",
                            "usage": {"input_tokens": 100, "total_tokens": 110},
                            "turn_token_usage": {
                                "input_tokens": 100,
                                "total_tokens": 110,
                            },
                            "thread_token_usage": {
                                "input_tokens": 100,
                                "total_tokens": 110,
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 100,
                                    "total_tokens": 110,
                                },
                                "last_token_usage": {
                                    "input_tokens": 100,
                                    "total_tokens": 110,
                                },
                                "model_context_window": 1000,
                            },
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    monkeypatch.setenv("TOKEN_COUNTER_DATA_DIR", str(data_dir))  # type: ignore[attr-defined]
    payload = {
        "hook_event_name": "Stop",
        "session_id": "session-1",
        "turn_id": "turn-1",
        "transcript_path": str(transcript),
        "model": "gpt-5.6-sol",
        "stop_hook_active": False,
    }
    stdout = StringIO()
    assert main(StringIO(json.dumps(payload)), stdout) == 0
    result = json.loads(stdout.getvalue())
    assert result["continue"] is True
    assert "• Total: 110 tokens" in result["systemMessage"]
    assert "• Context: 100 / 1,000 tokens" in result["systemMessage"]

    duplicate_stdout = StringIO()
    assert main(StringIO(json.dumps(payload)), duplicate_stdout) == 0
    assert duplicate_stdout.getvalue() == ""


def test_prompt_baseline_is_used_when_turn_record_is_missing(
    tmp_path: Path, monkeypatch: object
) -> None:
    transcript = tmp_path / "legacy-rollout.jsonl"
    baseline = {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": 90,
                    "output_tokens": 10,
                    "total_tokens": 100,
                },
                "last_token_usage": {
                    "input_tokens": 20,
                    "output_tokens": 5,
                    "total_tokens": 25,
                },
                "model_context_window": 1000,
            },
        },
    }
    transcript.write_text(json.dumps(baseline) + "\n", encoding="utf-8")
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "TOKEN_COUNTER_DATA_DIR", str(tmp_path / "data")
    )
    common = {
        "session_id": "legacy-session",
        "turn_id": "legacy-turn",
        "transcript_path": str(transcript),
        "model": "gpt-5.6-sol",
    }

    prompt_stdout = StringIO()
    assert (
        main(
            StringIO(json.dumps({**common, "hook_event_name": "UserPromptSubmit"})),
            prompt_stdout,
        )
        == 0
    )
    assert prompt_stdout.getvalue() == ""

    final = {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": 130,
                    "output_tokens": 20,
                    "total_tokens": 150,
                },
                "last_token_usage": {
                    "input_tokens": 40,
                    "output_tokens": 10,
                    "total_tokens": 50,
                },
                "model_context_window": 1000,
            },
        },
    }
    with transcript.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(final) + "\n")

    stop_stdout = StringIO()
    assert (
        main(StringIO(json.dumps({**common, "hook_event_name": "Stop"})), stop_stdout)
        == 0
    )
    result = json.loads(stop_stdout.getvalue())
    assert "• Turn: 50 tokens" in result["systemMessage"]


def test_missing_transcript_is_silent(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "TOKEN_COUNTER_DATA_DIR", str(tmp_path / "data")
    )
    payload = {
        "hook_event_name": "Stop",
        "session_id": "session",
        "turn_id": "turn",
        "transcript_path": str(tmp_path / "missing.jsonl"),
    }
    stdout = StringIO()
    assert main(StringIO(json.dumps(payload)), stdout) == 0
    assert stdout.getvalue() == ""


def test_duplicate_prompt_preserves_earliest_baseline(
    tmp_path: Path, monkeypatch: object
) -> None:
    transcript = tmp_path / "rollout.jsonl"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("TOKEN_COUNTER_DATA_DIR", str(data_dir))  # type: ignore[attr-defined]
    common = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "retry-session",
        "turn_id": "turn-1",
        "transcript_path": str(transcript),
        "model": "gpt-5.6-sol",
    }

    for total in (100, 140):
        transcript.write_text(
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": total,
                                "total_tokens": total,
                            }
                        },
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert main(StringIO(json.dumps(common)), StringIO()) == 0

    assert StateStore(data_dir).load("retry-session").baseline == TokenBreakdown(
        input_tokens=100,
        total_tokens=100,
    )


def test_interrupt_clears_only_matching_pending_turn(
    tmp_path: Path, monkeypatch: object
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("TOKEN_COUNTER_DATA_DIR", str(data_dir))  # type: ignore[attr-defined]
    store = StateStore(data_dir)
    store.save(
        "session",
        SessionState(
            turn_id="turn-1",
            baseline=TokenBreakdown(total_tokens=100),
            reported_turn_id="turn-0",
        ),
    )

    wrong_turn = {
        "hook_event_name": "Interrupt",
        "session_id": "session",
        "turn_id": "other-turn",
    }
    assert main(StringIO(json.dumps(wrong_turn)), StringIO()) == 0
    assert store.load("session").turn_id == "turn-1"

    matching_turn = {**wrong_turn, "turn_id": "turn-1"}
    assert main(StringIO(json.dumps(matching_turn)), StringIO()) == 0
    assert store.load("session") == SessionState(reported_turn_id="turn-0")


def test_resume_clears_pending_baseline_but_compact_preserves_it(
    tmp_path: Path, monkeypatch: object
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("TOKEN_COUNTER_DATA_DIR", str(data_dir))  # type: ignore[attr-defined]
    store = StateStore(data_dir)
    pending = SessionState(
        turn_id="turn-1",
        baseline=TokenBreakdown(total_tokens=100),
        reported_turn_id="turn-0",
    )
    store.save("session", pending)

    compact = {
        "hook_event_name": "SessionStart",
        "session_id": "session",
        "source": "compact",
    }
    assert main(StringIO(json.dumps(compact)), StringIO()) == 0
    assert store.load("session") == pending

    resume = {**compact, "source": "resume"}
    assert main(StringIO(json.dumps(resume)), StringIO()) == 0
    assert store.load("session") == SessionState(reported_turn_id="turn-0")


def test_concurrent_duplicate_stop_emits_once(
    tmp_path: Path, monkeypatch: object
) -> None:
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 90,
                            "output_tokens": 10,
                            "total_tokens": 100,
                        },
                        "last_token_usage": {
                            "input_tokens": 90,
                            "output_tokens": 10,
                            "total_tokens": 100,
                        },
                        "model_context_window": 1000,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(  # type: ignore[attr-defined]
        "TOKEN_COUNTER_DATA_DIR", str(tmp_path / "data")
    )
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "session_id": "concurrent-session",
            "turn_id": "turn-1",
            "transcript_path": str(transcript),
            "model": "gpt-5.6-sol",
        }
    )

    def invoke() -> str:
        stdout = StringIO()
        assert main(StringIO(payload), stdout) == 0
        return stdout.getvalue()

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = list(executor.map(lambda _: invoke(), range(16)))

    reports = [output for output in outputs if output]
    assert len(reports) == 1
    result = json.loads(reports[0])
    assert "• Total: 100 tokens" in result["systemMessage"]
