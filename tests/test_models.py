from token_counter.models import TokenBreakdown


def test_token_breakdown_accepts_snake_and_camel_case() -> None:
    snake = TokenBreakdown.from_mapping(
        {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
    )
    camel = TokenBreakdown.from_mapping(
        {"inputTokens": 10, "outputTokens": 2, "totalTokens": 12}
    )
    assert (
        snake
        == camel
        == TokenBreakdown(input_tokens=10, output_tokens=2, total_tokens=12)
    )


def test_subtract_clamps_negative_values() -> None:
    current = TokenBreakdown(input_tokens=5, total_tokens=7)
    baseline = TokenBreakdown(input_tokens=8, output_tokens=1, total_tokens=9)
    assert current.subtract(baseline) == TokenBreakdown()
