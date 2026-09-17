"""Model-specific Codex credit-rate loading and calculation."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .models import TokenBreakdown, UsageRecord

MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class ModelRate:
    name: str
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal
    aliases: frozenset[str]
    speed_multipliers: Mapping[str, Decimal]


@dataclass(frozen=True, slots=True)
class CreditEstimate:
    credits: Decimal | None
    source: str
    unknown_models: tuple[str, ...] = ()


class RateTable:
    def __init__(self, rates: Mapping[str, ModelRate]) -> None:
        self._rates = dict(rates)
        self._aliases: dict[str, ModelRate] = {}
        for rate in rates.values():
            self._aliases[rate.name] = rate
            for alias in rate.aliases:
                self._aliases[alias] = rate

    @classmethod
    def load(cls, path: str | Path) -> RateTable:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise ValueError("rate table must be a JSON object")
        raw_models = payload.get("models")
        if not isinstance(raw_models, Mapping):
            raise ValueError("rate table models must be a JSON object")
        rates: dict[str, ModelRate] = {}
        for name, raw in raw_models.items():
            if not isinstance(name, str) or not isinstance(raw, Mapping):
                continue
            aliases = raw.get("aliases", [])
            multipliers = raw.get("speed_multipliers", {})
            rates[name] = ModelRate(
                name=name,
                input_per_million=Decimal(str(raw["input"])),
                cached_input_per_million=Decimal(str(raw["cached_input"])),
                output_per_million=Decimal(str(raw["output"])),
                aliases=frozenset(alias for alias in aliases if isinstance(alias, str)),
                speed_multipliers={
                    str(key): Decimal(str(value))
                    for key, value in (
                        multipliers.items() if isinstance(multipliers, Mapping) else []
                    )
                },
            )
        return cls(rates)

    def calculate(
        self,
        tokens: TokenBreakdown,
        *,
        model: str | None,
        service_tier: str | None,
    ) -> Decimal | None:
        if model is None:
            return None
        rate = self._aliases.get(model)
        if rate is None:
            return None
        multiplier = Decimal(1)
        if service_tier not in (None, "", "standard", "default"):
            configured = rate.speed_multipliers.get(service_tier)
            if configured is None:
                return None
            multiplier = configured
        cached = min(tokens.cached_input_tokens, tokens.input_tokens)
        non_cached = max(tokens.input_tokens - cached, 0)
        base = (
            Decimal(non_cached) * rate.input_per_million
            + Decimal(cached) * rate.cached_input_per_million
            + Decimal(tokens.output_tokens) * rate.output_per_million
        ) / MILLION
        return base * multiplier

    def calculate_records(
        self,
        records: tuple[UsageRecord, ...],
        *,
        turn_id: str | None = None,
    ) -> CreditEstimate:
        total = Decimal(0)
        unknown: set[str] = set()
        matched = False
        for record in records:
            if turn_id is not None and record.turn_id != turn_id:
                continue
            matched = True
            value = self.calculate(
                record.usage,
                model=record.model,
                service_tier=record.service_tier,
            )
            if value is None:
                unknown.add(record.model or "unknown")
                continue
            total += value
        if not matched or unknown:
            return CreditEstimate(
                credits=None,
                source="local-rate-table",
                unknown_models=tuple(sorted(unknown)),
            )
        return CreditEstimate(credits=total, source="local-rate-table")


def default_rate_table_path() -> Path:
    override = os.environ.get("TOKEN_COUNTER_RATES_PATH")
    if override:
        return Path(override).expanduser()
    source_tree = Path(__file__).resolve().parents[2] / "config" / "model_rates.json"
    if source_tree.is_file():
        return source_tree
    return Path(__file__).resolve().parent / "data" / "model_rates.json"
