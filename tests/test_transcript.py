import json
from pathlib import Path

from token_counter.models import TokenBreakdown
from token_counter.transcript import read_usage_snapshot


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )


def test_reads_turn_thread_and_context_usage(tmp_path: Path) -> None:
    transcript = tmp_path / "rollout.jsonl"
    _write_jsonl(
        transcript,
        [
            {
                "type": "turn_context",
                "payload": {
                    "turn_id": "turn-1",
                    "model": "gpt-5.6-sol",
                    "effort": "high",
                    "service_tier": None,
                },
            },
            {
                "type": "token_usage_record",
                "payload": {
                    "turn_id": "turn-1",
                    "usage": {
                        "input_tokens": 80,
                        "cached_input_tokens": 50,
                        "output_tokens": 20,
                        "total_tokens": 100,
                    },
                    "turn_token_usage": {
                        "input_tokens": 80,
                        "cached_input_tokens": 50,
                        "output_tokens": 20,
                        "total_tokens": 100,
                    },
                    "thread_token_usage": {
                        "input_tokens": 800,
                        "cached_input_tokens": 500,
                        "output_tokens": 200,
                        "total_tokens": 1000,
                    },
                },
            },
            {"broken": "record"},
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 800,
                            "cached_input_tokens": 500,
                            "output_tokens": 200,
                            "total_tokens": 1000,
                        },
                        "last_token_usage": {
                            "input_tokens": 80,
                            "cached_input_tokens": 50,
                            "output_tokens": 20,
                            "total_tokens": 100,
                        },
                        "model_context_window": 1000,
                    },
                },
            },
        ],
    )

    snapshot = read_usage_snapshot(transcript, turn_id="turn-1")

    assert snapshot.thread_usage == TokenBreakdown(
        input_tokens=800,
        cached_input_tokens=500,
        output_tokens=200,
        total_tokens=1000,
    )
    assert snapshot.turn_usage is not None
    assert snapshot.turn_usage.total_tokens == 100
    assert snapshot.last_usage is not None
    assert snapshot.last_usage.input_tokens == 80
    assert snapshot.model_context_window == 1000
    assert snapshot.model == "gpt-5.6-sol"
    assert snapshot.reasoning_effort == "high"


def test_skips_truncated_jsonl_line(tmp_path: Path) -> None:
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text(
        '{"type":"event_msg","payload":{"type":"token_count","info":\n',
        encoding="utf-8",
    )
    snapshot = read_usage_snapshot(transcript, turn_id="turn-1")
    assert snapshot.thread_usage is None
