import json
from io import StringIO
from pathlib import Path

from token_counter.cli import main


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
    assert "Total: 110 tokens" in result["systemMessage"]
    assert "Context: 100 / 1,000 tokens" in result["systemMessage"]

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
    assert "Turn:  50 tokens" in result["systemMessage"]


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
