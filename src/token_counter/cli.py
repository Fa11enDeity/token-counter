"""Codex hook command entry point."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

from .formatter import format_report
from .models import HookPayload, TokenBreakdown, UsageSnapshot
from .rates import CreditEstimate, RateTable, default_rate_table_path
from .state import SessionState, StateStore
from .transcript import read_latest_thread_usage, read_usage_snapshot


def _empty_estimate() -> CreditEstimate:
    return CreditEstimate(credits=None, source="unavailable")


def _snapshot(payload: HookPayload) -> UsageSnapshot | None:
    if payload.transcript_path is None:
        return None
    path = Path(payload.transcript_path)
    if not path.is_file():
        return None
    return read_usage_snapshot(
        path,
        turn_id=payload.turn_id,
        fallback_model=payload.model,
    )


def _turn_usage(
    snapshot: UsageSnapshot,
    state: SessionState,
    turn_id: str | None,
) -> TokenBreakdown | None:
    if snapshot.turn_usage is not None:
        return snapshot.turn_usage
    if (
        snapshot.thread_usage is not None
        and state.baseline is not None
        and state.turn_id == turn_id
    ):
        return snapshot.thread_usage.subtract(state.baseline)
    return snapshot.last_usage


def process_hook(payload: HookPayload, store: StateStore) -> dict[str, object] | None:
    if payload.event_name == "SessionStart":
        store.cleanup_stale(exclude_session_id=payload.session_id)
        if payload.source == "compact":
            return None
        with store.locked(payload.session_id):
            state = store.load(payload.session_id)
            if payload.source == "resume":
                store.save(
                    payload.session_id,
                    SessionState(reported_turn_id=state.reported_turn_id),
                )
            else:
                store.save(payload.session_id, SessionState())
        return None

    if payload.event_name == "Interrupt":
        with store.locked(payload.session_id):
            state = store.load(payload.session_id)
            if payload.turn_id is None or state.turn_id == payload.turn_id:
                store.save(
                    payload.session_id,
                    SessionState(reported_turn_id=state.reported_turn_id),
                )
        return None

    if payload.event_name == "UserPromptSubmit":
        store.cleanup_stale(exclude_session_id=payload.session_id)
        with store.locked(payload.session_id):
            state = store.load(payload.session_id)
            baseline = None
            if payload.transcript_path is not None:
                path = Path(payload.transcript_path)
                if path.is_file():
                    baseline = read_latest_thread_usage(path)
            if state.turn_id == payload.turn_id and state.baseline is not None:
                baseline = state.baseline
            store.save(
                payload.session_id,
                SessionState(
                    turn_id=payload.turn_id,
                    baseline=baseline,
                    reported_turn_id=state.reported_turn_id,
                ),
            )
        return None

    snapshot = _snapshot(payload)

    if payload.event_name != "Stop" or snapshot is None:
        return None

    with store.locked(payload.session_id):
        state = store.load(payload.session_id)
        if payload.turn_id is not None and state.reported_turn_id == payload.turn_id:
            return None

        turn_usage = _turn_usage(snapshot, state, payload.turn_id)
        try:
            rates = RateTable.load(default_rate_table_path())
            thread_credits = rates.calculate_records(snapshot.records)
            turn_credits = rates.calculate_records(
                snapshot.records, turn_id=payload.turn_id
            )
            if not snapshot.records:
                thread_credits = CreditEstimate(
                    credits=rates.calculate(
                        snapshot.thread_usage or TokenBreakdown(),
                        model=snapshot.model,
                        service_tier=snapshot.service_tier,
                    ),
                    source="local-rate-table",
                )
                turn_credits = CreditEstimate(
                    credits=rates.calculate(
                        turn_usage or TokenBreakdown(),
                        model=snapshot.model,
                        service_tier=snapshot.service_tier,
                    ),
                    source="local-rate-table",
                )
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            thread_credits = _empty_estimate()
            turn_credits = _empty_estimate()

        message = format_report(
            snapshot,
            turn_usage=turn_usage,
            thread_credits=thread_credits,
            turn_credits=turn_credits,
        )
        store.save(
            payload.session_id,
            SessionState(
                turn_id=state.turn_id,
                baseline=state.baseline,
                reported_turn_id=payload.turn_id,
            ),
        )
    return {"continue": True, "systemMessage": message, "suppressOutput": False}


def main(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    try:
        raw = json.load(stdin)
        payload = HookPayload.from_mapping(raw)
        output = process_hook(payload, StateStore())
        if output is not None:
            json.dump(output, stdout, separators=(",", ":"))
            stdout.write("\n")
        return 0
    except Exception as error:  # Hooks must never prevent Codex from completing a turn.
        print(f"token-counter: {error}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
