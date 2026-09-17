"""Internal data models with tolerant Codex wire-format parsing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float) and value.is_integer():
        return max(int(value), 0)
    return 0


def _first(mapping: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


@dataclass(frozen=True, slots=True)
class TokenBreakdown:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_mapping(cls, value: object) -> TokenBreakdown | None:
        if not isinstance(value, Mapping):
            return None
        result = cls(
            input_tokens=_non_negative_int(
                _first(value, "input_tokens", "inputTokens")
            ),
            cached_input_tokens=_non_negative_int(
                _first(value, "cached_input_tokens", "cachedInputTokens")
            ),
            cache_write_input_tokens=_non_negative_int(
                _first(value, "cache_write_input_tokens", "cacheWriteInputTokens")
            ),
            output_tokens=_non_negative_int(
                _first(value, "output_tokens", "outputTokens")
            ),
            reasoning_output_tokens=_non_negative_int(
                _first(value, "reasoning_output_tokens", "reasoningOutputTokens")
            ),
            total_tokens=_non_negative_int(
                _first(value, "total_tokens", "totalTokens")
            ),
        )
        if result.total_tokens == 0:
            result = cls(
                input_tokens=result.input_tokens,
                cached_input_tokens=result.cached_input_tokens,
                cache_write_input_tokens=result.cache_write_input_tokens,
                output_tokens=result.output_tokens,
                reasoning_output_tokens=result.reasoning_output_tokens,
                total_tokens=result.input_tokens + result.output_tokens,
            )
        return result

    def subtract(self, baseline: TokenBreakdown) -> TokenBreakdown:
        return TokenBreakdown(
            input_tokens=max(self.input_tokens - baseline.input_tokens, 0),
            cached_input_tokens=max(
                self.cached_input_tokens - baseline.cached_input_tokens, 0
            ),
            cache_write_input_tokens=max(
                self.cache_write_input_tokens - baseline.cache_write_input_tokens, 0
            ),
            output_tokens=max(self.output_tokens - baseline.output_tokens, 0),
            reasoning_output_tokens=max(
                self.reasoning_output_tokens - baseline.reasoning_output_tokens, 0
            ),
            total_tokens=max(self.total_tokens - baseline.total_tokens, 0),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True, slots=True)
class HookPayload:
    event_name: str
    session_id: str
    turn_id: str | None
    transcript_path: str | None
    model: str | None
    stop_hook_active: bool = False

    @classmethod
    def from_mapping(cls, value: object) -> HookPayload:
        if not isinstance(value, Mapping):
            raise ValueError("hook input must be a JSON object")
        event_name = value.get("hook_event_name")
        session_id = value.get("session_id")
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("hook_event_name is required")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id is required")
        turn_id = value.get("turn_id")
        transcript_path = value.get("transcript_path")
        model = value.get("model")
        return cls(
            event_name=event_name,
            session_id=session_id,
            turn_id=turn_id if isinstance(turn_id, str) else None,
            transcript_path=(
                transcript_path if isinstance(transcript_path, str) else None
            ),
            model=model if isinstance(model, str) else None,
            stop_hook_active=value.get("stop_hook_active") is True,
        )


@dataclass(frozen=True, slots=True)
class TurnContext:
    turn_id: str
    model: str | None
    reasoning_effort: str | None
    service_tier: str | None


@dataclass(frozen=True, slots=True)
class UsageRecord:
    turn_id: str | None
    usage: TokenBreakdown
    turn_usage: TokenBreakdown | None
    thread_usage: TokenBreakdown | None
    model: str | None
    reasoning_effort: str | None
    service_tier: str | None


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    thread_usage: TokenBreakdown | None
    turn_usage: TokenBreakdown | None
    last_usage: TokenBreakdown | None
    model_context_window: int | None
    model: str | None
    reasoning_effort: str | None
    service_tier: str | None
    records: tuple[UsageRecord, ...]
