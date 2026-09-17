# Compatibility

## Current Development Baseline

- Codex CLI/Desktop runtime: `0.155.0-alpha.2.6`
- Hook feature status: stable in the tested Codex runtime
- Python: 3.11 and newer
- Development platform: macOS arm64 with Python 3.12.14
- CI targets: macOS, Linux, and Windows on Python 3.11 and 3.12

## Codex Data Compatibility

The parser accepts snake_case and camelCase token fields and skips unknown JSONL records. The tested runtime includes `token_usage_record`, `event_msg.token_count`, and `turn_context` records.

Older transcripts without `token_usage_record.turn_token_usage` use the lifecycle baseline fallback. A transcript without any cumulative token event cannot produce a report.

The state adapter handles duplicate prompt and stop delivery, explicit `Interrupt` events, and `SessionStart` sources including `resume` and `compact`. Unexpected process termination cannot emit an `Interrupt`; the next `resume` event therefore clears any pending fallback baseline before another turn begins.

## Authentication and Billing

Raw token and context accounting is local and independent of ChatGPT billing mode. The documented App Server `account/usage/read` method currently exposes account-level token activity, not per-thread credits. Local rate calculations are therefore the only credit source and require an exact configured model and speed tier.

Plus and Pro rate-limit windows are not inferred from raw tokens. They require a separate server-provided rate-limit value.

## Platform Notes

The POSIX hook command uses `scripts/run-token-counter`. It prefers a plugin-local `.venv`, then a system Python 3.11+, then `uv` from `PATH` or the default `~/.local/bin/uv` installation path. The Windows command uses the Python launcher (`py -3`) and still requires an installed Python 3.11+ runtime. Windows command expansion and installed-client rendering have not yet been manually verified.
