"""Compact user-facing usage report formatting."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .models import TokenBreakdown, UsageSnapshot
from .rates import CreditEstimate


def _tokens(value: int) -> str:
    return f"{value:,}"


def _credits(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.2f}"


def format_report(
    snapshot: UsageSnapshot,
    *,
    turn_usage: TokenBreakdown | None,
    thread_credits: CreditEstimate,
    turn_credits: CreditEstimate,
) -> str:
    lines = ["Token Counter"]
    if snapshot.thread_usage is not None:
        lines.append(
            "• Total: "
            f"{_tokens(snapshot.thread_usage.total_tokens)} tokens | "
            f"{_credits(thread_credits.credits)} credits"
        )
    if turn_usage is not None:
        lines.append(
            "• Turn: "
            f"{_tokens(turn_usage.total_tokens)} tokens | "
            f"{_credits(turn_credits.credits)} credits"
        )
    if snapshot.last_usage is not None and snapshot.model_context_window is not None:
        used = snapshot.last_usage.input_tokens
        window = snapshot.model_context_window
        remaining = max(window - used, 0)
        percentage = Decimal(remaining * 100) / Decimal(window)
        lines.append(f"• Context: {_tokens(used)} / {_tokens(window)} tokens")
        lines.append(
            f"• Remaining: {_tokens(remaining)} tokens | "
            f"{percentage.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"
        )
    model_parts = [part for part in (snapshot.model, snapshot.reasoning_effort) if part]
    if snapshot.service_tier:
        model_parts.append(snapshot.service_tier)
    if model_parts:
        lines.append("• Model: " + " | ".join(model_parts))
    return "\n".join(lines)
