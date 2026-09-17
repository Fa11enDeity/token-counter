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

## Authentication and Billing

Raw token and context accounting is local and independent of ChatGPT billing mode. Server-estimated thread credits may be unavailable depending on authentication and billing route. Local rate calculations remain available when the active model and speed tier have an exact configured rate.

Plus and Pro rate-limit windows are not inferred from raw tokens. They require a separate server-provided rate-limit value.

## Platform Notes

The POSIX hook command uses `python3`. The Windows command uses the Python launcher (`py -3`) and still requires an installed Python 3.11+ runtime. Windows command expansion and installed-client rendering have not yet been manually verified.
