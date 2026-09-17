"""Extract token usage from Codex JSONL transcripts.

The transcript is an explicitly unstable convenience interface. All parsing is
therefore tolerant: unknown records are ignored and both snake_case and
camelCase token fields are accepted.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from .models import (
    TokenBreakdown,
    TurnContext,
    UsageRecord,
    UsageSnapshot,
)


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def iter_jsonl(path: Path) -> Iterator[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(value, Mapping):
                yield value


def iter_jsonl_reverse(
    path: Path, *, chunk_size: int = 64 * 1024
) -> Iterator[Mapping[str, Any]]:
    """Read complete JSONL records newest-first without loading the whole file."""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        remainder = b""
        while position > 0:
            read_size = min(chunk_size, position)
            position -= read_size
            handle.seek(position)
            block = handle.read(read_size) + remainder
            lines = block.split(b"\n")
            remainder = lines[0]
            for line in reversed(lines[1:]):
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    continue
                if isinstance(value, Mapping):
                    yield value
        if remainder:
            try:
                value = json.loads(remainder)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                return
            if isinstance(value, Mapping):
                yield value


def read_latest_thread_usage(transcript_path: str | Path) -> TokenBreakdown | None:
    """Return the newest cumulative usage record using a bounded reverse scan."""
    for item in iter_jsonl_reverse(Path(transcript_path)):
        payload = _mapping(item.get("payload"))
        if item.get("type") == "token_usage_record" and payload is not None:
            usage = TokenBreakdown.from_mapping(payload.get("thread_token_usage"))
            if usage is not None:
                return usage
        if (
            item.get("type") == "event_msg"
            and payload is not None
            and payload.get("type") == "token_count"
        ):
            info = _mapping(payload.get("info"))
            if info is None:
                continue
            usage = TokenBreakdown.from_mapping(info.get("total_token_usage"))
            if usage is not None:
                return usage
    return None


def read_usage_snapshot(
    transcript_path: str | Path,
    *,
    turn_id: str | None,
    fallback_model: str | None = None,
) -> UsageSnapshot:
    contexts: dict[str, TurnContext] = {}
    raw_records: list[tuple[str | None, Mapping[str, Any]]] = []
    latest_total: TokenBreakdown | None = None
    latest_last: TokenBreakdown | None = None
    context_window: int | None = None

    for item in iter_jsonl(Path(transcript_path)):
        item_type = item.get("type")
        payload = _mapping(item.get("payload"))

        if item_type == "turn_context" and payload is not None:
            context_turn_id = _string(payload.get("turn_id"))
            if context_turn_id is not None:
                contexts[context_turn_id] = TurnContext(
                    turn_id=context_turn_id,
                    model=_string(payload.get("model")),
                    reasoning_effort=_string(payload.get("effort")),
                    service_tier=_string(payload.get("service_tier")),
                )
            continue

        if item_type == "token_usage_record" and payload is not None:
            raw_records.append((_string(payload.get("turn_id")), payload))
            thread = TokenBreakdown.from_mapping(payload.get("thread_token_usage"))
            if thread is not None:
                latest_total = thread
            continue

        if (
            item_type == "event_msg"
            and payload is not None
            and payload.get("type") == "token_count"
        ):
            info = _mapping(payload.get("info"))
            if info is None:
                continue
            total = TokenBreakdown.from_mapping(info.get("total_token_usage"))
            last = TokenBreakdown.from_mapping(info.get("last_token_usage"))
            if total is not None:
                latest_total = total
            if last is not None:
                latest_last = last
            context_window = _positive_int(info.get("model_context_window"))

    records: list[UsageRecord] = []
    matching_turn_usage: TokenBreakdown | None = None
    selected_context = contexts.get(turn_id) if turn_id is not None else None

    for record_turn_id, payload in raw_records:
        context = contexts.get(record_turn_id) if record_turn_id is not None else None
        usage = TokenBreakdown.from_mapping(payload.get("usage"))
        if usage is None:
            continue
        record = UsageRecord(
            turn_id=record_turn_id,
            usage=usage,
            turn_usage=TokenBreakdown.from_mapping(payload.get("turn_token_usage")),
            thread_usage=TokenBreakdown.from_mapping(payload.get("thread_token_usage")),
            model=context.model if context is not None else None,
            reasoning_effort=(
                context.reasoning_effort if context is not None else None
            ),
            service_tier=context.service_tier if context is not None else None,
        )
        records.append(record)
        if turn_id is not None and record_turn_id == turn_id:
            matching_turn_usage = record.turn_usage or usage

    return UsageSnapshot(
        thread_usage=latest_total,
        turn_usage=matching_turn_usage,
        last_usage=latest_last,
        model_context_window=context_window,
        model=(selected_context.model if selected_context else fallback_model),
        reasoning_effort=(
            selected_context.reasoning_effort if selected_context else None
        ),
        service_tier=selected_context.service_tier if selected_context else None,
        records=tuple(records),
    )
