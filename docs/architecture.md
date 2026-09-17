# Architecture

## Lifecycle

Token Counter uses four Codex command hooks:

```text
UserPromptSubmit -> capture cumulative baseline -> Codex turn runs
Stop             -> read final usage -> calculate -> emit systemMessage
Interrupt        -> discard the interrupted turn's pending baseline
SessionStart     -> reconcile state after startup, resume, clear, or compaction
```

The hook process is short-lived. Persistent state contains only session and turn identifiers, a token baseline, and the last reported turn identifier. Prompt and response text are never copied into state.

## Data Sources

The alpha implementation reads the transcript path supplied by the [official hook payload](https://learn.chatgpt.com/docs/hooks#common-input-fields). Transcript JSONL is not a stable public interface, so parsing is isolated in `transcript.py` and ignores unknown or malformed records.

The preferred records are:

- `token_usage_record.usage`: one model request.
- `token_usage_record.turn_token_usage`: cumulative usage for the current turn.
- `token_usage_record.thread_token_usage`: cumulative usage for the thread.
- `event_msg.token_count.info.last_token_usage`: latest active context request.
- `event_msg.token_count.info.model_context_window`: effective context window.
- `turn_context`: model, reasoning effort, and service tier for a turn.

When `turn_token_usage` is unavailable, the hook subtracts the baseline captured by `UserPromptSubmit` from the final cumulative thread usage.

`UserPromptSubmit` finds that baseline with a bounded, reverse JSONL scan and stops at the newest complete cumulative record. `Stop` still scans the complete transcript because cumulative credits must preserve the model and speed tier of every request; a future cursor format can optimize that path only if it retains the same accounting guarantees.

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

## App Server Decision

The current official [App Server contract](https://learn.chatgpt.com/docs/app-server#7-token-usage-chatgpt) defines `account/usage/read` as an account-level token-activity summary. It can return lifetime tokens, peak daily tokens, turn duration and streak fields, plus optional daily buckets. It does not accept a thread identifier or expose per-thread estimated credits in the documented contract.

Token Counter therefore does not launch a second App Server process from a hook. Per-thread and per-turn credits use the local, versioned rate table. A future server adapter will be added only if OpenAI publishes a stable thread-credit field suitable for lifecycle hooks.

## Failure Behavior

Hook failures are non-blocking. Invalid input, an unavailable transcript, an unknown record shape, an unwritable state directory, or an invalid rate table causes the hook to exit successfully without stopping the Codex turn. Unknown models affect only the credit value; raw token and context metrics remain available.

State writes use atomic replacement and a per-session process lock. The lock makes duplicate `Stop` detection and the corresponding state update one operation, so concurrent delivery produces at most one report. On prompt submission, state files older than 30 days are removed; the current session and any state file whose lock is held are skipped.

Repeated `UserPromptSubmit` delivery for the same turn preserves the earliest baseline. An `Interrupt` clears a matching unfinished turn without erasing the last reported turn identifier. `SessionStart` with `resume` performs the same pending-state cleanup, while `compact` deliberately preserves the active baseline because compaction can occur in the middle of a turn. `startup` and `clear` reset the session state.
