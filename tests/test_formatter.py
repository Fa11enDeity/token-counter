from decimal import Decimal

from token_counter.formatter import format_report
from token_counter.models import TokenBreakdown, UsageSnapshot
from token_counter.rates import CreditEstimate


def test_formats_complete_report() -> None:
    snapshot = UsageSnapshot(
        thread_usage=TokenBreakdown(total_tokens=10_000),
        turn_usage=TokenBreakdown(total_tokens=500),
        last_usage=TokenBreakdown(input_tokens=750, total_tokens=800),
        model_context_window=1_000,
        model="gpt-5.6-sol",
        reasoning_effort="high",
        service_tier=None,
        records=(),
    )
    report = format_report(
        snapshot,
        turn_usage=snapshot.turn_usage,
        thread_credits=CreditEstimate(Decimal("1.234"), "test"),
        turn_credits=CreditEstimate(Decimal("0.056"), "test"),
    )
    assert "Total: 10,000 tokens | 1.23 credits" in report
    assert "Turn:  500 tokens | 0.06 credits" in report
    assert "Remain:  250 tokens | 25.0%" in report
    assert "Model: gpt-5.6-sol | high" in report
