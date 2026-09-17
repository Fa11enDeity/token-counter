# Architecture

## Lifecycle

Token Counter runs as two Codex command hooks:

```text
UserPromptSubmit -> capture cumulative baseline -> Codex turn runs
Stop             -> read final usage -> calculate -> emit systemMessage
```

The hook process is short-lived. Persistent state contains only session and turn identifiers, a token baseline, and the last reported turn identifier. Prompt and response text are never copied into state.

## Data Sources

The alpha implementation reads the transcript path supplied by the official hook payload. Transcript JSONL is not a stable public interface, so parsing is isolated in `transcript.py` and ignores unknown or malformed records.

The preferred records are:

- `token_usage_record.usage`: one model request.
- `token_usage_record.turn_token_usage`: cumulative usage for the current turn.
- `token_usage_record.thread_token_usage`: cumulative usage for the thread.
- `event_msg.token_count.info.last_token_usage`: latest active context request.
- `event_msg.token_count.info.model_context_window`: effective context window.
- `turn_context`: model, reasoning effort, and service tier for a turn.

When `turn_token_usage` is unavailable, the hook subtracts the baseline captured by `UserPromptSubmit` from the final cumulative thread usage.

## Credit Accounting

Credits are calculated per model request and then summed. This avoids applying the latest model's rate to an earlier request made with another model.

```text
non_cached_input = max(input - cached_input, 0)

credits = (
  non_cached_input * input_rate
  + cached_input * cached_input_rate
  + output * output_rate
) / 1,000,000
```

Reasoning-output tokens are informational and are not added separately because they are represented within output usage. Decimal arithmetic is used throughout.

An exact model and speed-tier match is required. Unknown combinations produce `n/a` rather than borrowing a similar model's rate.

## Server Usage Experiment

Codex App Server exposes experimental `account/usage/read` parameters that accept a thread ID and may return `estimatedUsageCreditsMicros`. A successful query against the development account returned `threadUsage: null`, which is valid when the current billing route does not expose an estimate. The alpha therefore does not launch App Server on every turn; doing so would add latency without guaranteeing a value.

Server-estimated credits remain a planned optional source. Local rate accounting is required even after that integration is added.

## Failure Behavior

Hook failures are non-blocking. Invalid input, an unavailable transcript, an unknown record shape, an unwritable state directory, or an invalid rate table causes the hook to exit successfully without stopping the Codex turn. Unknown models affect only the credit value; raw token and context metrics remain available.
