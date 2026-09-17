from decimal import Decimal

from token_counter.models import TokenBreakdown, UsageRecord
from token_counter.rates import RateTable, default_rate_table_path


def test_sol_credit_calculation_uses_cached_rate() -> None:
    table = RateTable.load(default_rate_table_path())
    tokens = TokenBreakdown(
        input_tokens=1_000,
        cached_input_tokens=400,
        output_tokens=100,
        total_tokens=1_100,
    )
    assert table.calculate(tokens, model="gpt-5.6-sol", service_tier=None) == Decimal(
        "0.114"
    )


def test_astra_fast_multiplier() -> None:
    table = RateTable.load(default_rate_table_path())
    tokens = TokenBreakdown(input_tokens=1_000_000, total_tokens=1_000_000)
    assert table.calculate(tokens, model="gpt-6-astra", service_tier="fast") == Decimal(
        "625.0"
    )


def test_unknown_model_makes_aggregate_unavailable() -> None:
    table = RateTable.load(default_rate_table_path())
    record = UsageRecord(
        turn_id="turn",
        usage=TokenBreakdown(input_tokens=10, total_tokens=10),
        turn_usage=None,
        thread_usage=None,
        model="future-model",
        reasoning_effort=None,
        service_tier=None,
    )
    estimate = table.calculate_records((record,))
    assert estimate.credits is None
    assert estimate.unknown_models == ("future-model",)
