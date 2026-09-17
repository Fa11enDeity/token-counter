# Token Counter for Codex

Token Counter for Codex is a planned Codex lifecycle-hook plugin that reports token usage, context-window usage, and model-adjusted credit consumption after every completed Codex turn.

The repository now contains an alpha implementation with a validated plugin manifest, lifecycle hooks, local credit-rate accounting, process-safe state, automated tests, and a real-transcript smoke test. Installed-client UI verification remains in development.

## Project Goals

The plugin is intended to display the following information automatically after each Codex response:

1. Total raw tokens consumed by the current conversation.
2. Raw tokens consumed by the current user turn.
3. Tokens used by the latest active model context.
4. Tokens remaining in the model context window.
5. Total and per-turn usage converted to Codex credits using the active model, token category, and speed tier.
6. When available, server-reported five-hour and weekly usage-window information.

An example result may look like this:

```text
Token usage
• Total: 128,420 tokens | 18.73 credits
• Turn: 12,806 tokens | 2.14 credits
• Context: 81,390 / 272,000 tokens
• Remaining: 190,610 tokens | 70.1%
• Model: gpt-5.6-sol | high | standard
```

The exact presentation may change during implementation as Codex CLI and Desktop rendering behavior is verified.

## Current Alpha Capabilities

- Reads official `SessionStart`, `UserPromptSubmit`, `Stop`, and `Interrupt` hook payloads.
- Uses `token_usage_record` for exact per-turn and cumulative usage when available.
- Uses `event_msg.token_count` for the latest context size and context-window limit.
- Falls back to a cumulative baseline when a transcript lacks per-turn records.
- Calculates credits per model request, preserving correctness across model changes.
- Distinguishes non-cached input, cached input, and output rates.
- Supports the documented Astra Fast multiplier and refuses unknown multipliers.
- Writes only small session baselines to the plugin data directory.
- Suppresses duplicate reports for a repeated `Stop` event.
- Preserves the earliest baseline across duplicate prompts or retries and clears unfinished state on interruption or resume.
- Uses a bounded reverse scan to capture the pre-turn cumulative baseline.
- Resolves Python 3.11+ through a plugin virtual environment, the system, or uv on macOS/Linux.
- Fails open so a counter error does not prevent Codex from finishing a turn.

## Development Setup

The development environment uses Python 3.12 and `uv`:

```bash
uv python install 3.12
uv python pin 3.12
uv sync --locked --all-groups
```

Run the complete local quality gate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=token_counter --cov-report=term-missing
uv run python scripts/verify-plugin.py
```

The hook runtime itself has no third-party Python dependencies. Pytest, Ruff, mypy, coverage, Hatchling, and PyYAML are development-only dependencies.

## Product Boundaries

The project distinguishes between two different concepts:

- **Raw token usage:** measurable input, cached-input, output, and reasoning-output token counts reported by Codex.
- **Credits:** usage calculated from an explicit, versioned rate table for the active model and service tier.

ChatGPT Plus and Pro included-usage limits are not a fixed token-to-credit conversion. Model selection, context size, reasoning, tool calls, caching, task duration, and service configuration can all affect those limits. The plugin will therefore display server-reported rate-limit windows when available instead of presenting a locally inferred value as exact.

## Implementation Strategy

### 1. Package the feature as a Codex plugin

The project will use a Codex plugin manifest and plugin-bundled lifecycle hooks. The initial hook configuration will register:

- `SessionStart` to reconcile pending state after startup, resume, clear, or compaction.
- `UserPromptSubmit` to capture the cumulative-usage baseline before a turn starts.
- `Stop` to collect the final counters, calculate the turn delta, and display the report when Codex is about to finish the turn.
- `Interrupt` to discard the interrupted turn's pending baseline.

Plugin packaging keeps the hook installable across projects while still allowing project-local development and testing.

### 2. Use cumulative deltas for per-turn usage

A single user turn can contain multiple model requests because Codex may reason, invoke tools, process results, and call the model again. The last model request alone is therefore not the complete turn cost.

Per-turn usage will be calculated as:

```text
turn usage = cumulative usage at Stop - cumulative usage at UserPromptSubmit
```

State is keyed by Codex session and turn identifiers, protected by a per-session process lock, and written atomically to the plugin data directory.

### 3. Prefer structured Codex usage data

The implementation uses the most stable available data source in this order:

1. Version-tolerant parsing of the transcript referenced by the official hook payload.
2. A graceful partial report when a field is unavailable.

Codex currently exposes structured usage containing cumulative and latest token breakdowns plus the model context window. Transcript parsing will be isolated behind an adapter because the official documentation does not promise a stable transcript format.

### 4. Calculate context usage correctly

The latest request's input-token count will be treated as the active context size. Remaining context will be calculated as:

```text
remaining context = model context window - latest input tokens
```

Values will be clamped at zero and clearly marked unavailable if the model context window is not reported. Compaction and model-switch events will cause the calculation to use the newest available values.

### 5. Calculate credits from an explicit rate table

The current official [Codex App Server contract](https://learn.chatgpt.com/docs/app-server#7-token-usage-chatgpt) exposes account-level token activity but not per-thread estimated credits. The plugin therefore calculates credits from a versioned rate table:

```text
credits =
  non-cached input tokens * input rate
  + cached input tokens * cached-input rate
  + output tokens * output rate
```

Rates are expressed per one million tokens. Reasoning tokens will not be counted twice when they are already included in output tokens. Unknown models will still receive an accurate raw-token report, but their credit value will be shown as unavailable until a rate is configured.

### 6. Display without polluting the model context

The `Stop` hook will return the smallest Codex-supported UI/event message that reliably appears after a response. The implementation will avoid returning large model-visible context. CLI, Desktop, and non-interactive behavior will be tested separately because their rendering surfaces are not identical.

Every metric line starts with an explicit bullet. Clients that preserve newlines render a vertical list; clients that collapse whitespace still retain visible separators between metrics. The formatter does not depend on Markdown rendering in `systemMessage`.

### 7. Keep processing local and privacy-preserving

The default implementation will not send prompts, replies, or transcripts to third-party services. It will read only the minimum local metadata needed for usage accounting. Optional Codex account queries will use the existing Codex authentication path rather than collecting or storing credentials.

## Development Environment

### Runtime

- Python 3.11 or newer.
- Python standard library for the runtime path where practical.
- macOS and Linux as the initial supported platforms.
- Windows support through `commandWindows` after path, shell, and Python-launcher behavior is verified.
- A recent Codex release with stable lifecycle hooks enabled.

Python is planned because official Codex hook examples use command scripts, JSON processing is available in the standard library, startup cost is acceptable for a turn-completion hook, and the plugin can remain easy to inspect and modify.

### Development tools

- `uv` for repeatable local environment and dependency management.
- `pytest` for unit and integration tests.
- `pytest-cov` for coverage reporting.
- `ruff` for linting and formatting.
- `mypy` for static type checking.
- `pre-commit` as an optional contributor workflow.

These tools are configured in `pyproject.toml` and locked in `uv.lock`.

## Planned Repository Structure

```text
token-counter/
|-- .codex-plugin/
|   `-- plugin.json                 # Codex plugin manifest
|-- hooks/
|   `-- hooks.json                  # Session, prompt, stop, and interrupt hooks
|-- src/
|   `-- token_counter/
|       |-- __init__.py
|       |-- cli.py                  # Hook process entry point
|       |-- hook_input.py           # Hook payload validation
|       |-- transcript.py           # Version-tolerant usage extraction
|       |-- accounting.py           # Token and credit calculations
|       |-- rates.py                # Model/rate resolution
|       |-- state.py                # Per-session baseline and locking
|       |-- formatter.py            # Compact user-facing report
|       `-- models.py               # Typed internal data models
|-- config/
|   `-- model_rates.json            # Versioned fallback credit rates
|-- tests/
|   |-- fixtures/                   # Sanitized hook/transcript samples
|   |-- unit/
|   `-- integration/
|-- scripts/
|   |-- install-local.sh            # Local development install helper
|   `-- verify-plugin.py            # Manifest and hook validation
|-- docs/
|   |-- architecture.md
|   |-- compatibility.md
|   `-- troubleshooting.md
|-- pyproject.toml
|-- uv.lock
|-- CHANGELOG.md
|-- LICENSE
|-- README.md
`-- .gitignore
```

The exact structure may be adjusted as the transcript adapter and installation workflow mature.

## Configuration Goals

Planned user configuration includes:

- Enable or disable raw-token, credit, context, and rate-limit lines.
- Select compact or expanded output.
- Choose exact numbers, abbreviated numbers, or both.
- Include or exclude subagent usage where Codex exposes enough metadata.
- Override or add model credit rates.
- Configure behavior for unknown models and temporarily missing usage data.
- Enable diagnostic logging without recording prompt or response content.

The alpha release already supports a complete replacement rate table through:

```bash
export TOKEN_COUNTER_RATES_PATH=/absolute/path/to/model_rates.json
```

The replacement file uses the same schema as `config/model_rates.json`. Unknown models or speed tiers are reported with `n/a` credits rather than an inferred rate.

The App Server is intentionally not launched from the hook because its documented account-usage endpoint does not provide per-thread credits. See `docs/architecture.md` for the recorded decision.

## Reliability and Compatibility Goals

The implementation is expected to handle:

- Multiple model requests within one turn.
- Tool-heavy turns.
- Context compaction.
- Model, reasoning-effort, and speed-tier changes.
- Interrupted or failed turns.
- Concurrent hook invocations.
- Missing, delayed, malformed, or newer usage events.
- Session resume and stale local state.
- Codex CLI and Desktop differences.
- Unknown future models without producing incorrect credit values.

All persistent writes will use plugin-scoped data storage, file locking where needed, and atomic replacement. Runtime errors should never prevent Codex from completing a response.

## Planned Testing

The test suite will cover:

- Token breakdown normalization.
- Per-turn delta accounting.
- Credit conversion for cached and non-cached input.
- Fast-tier and model-specific rates.
- Context-used and context-remaining calculations.
- Model switches and compaction.
- Unknown models and missing fields.
- Concurrent state updates.
- Hook input/output contract fixtures.
- End-to-end execution against a temporary plugin data directory.
- Manual smoke tests in Codex CLI and Codex Desktop.

Fixture data will be synthetic or sanitized and will not contain real conversation content or credentials.

## Expected Deliverables

The initial stable release is expected to include:

1. An installable Codex plugin manifest and lifecycle-hook configuration.
2. A cross-platform hook runner for the supported platforms.
3. Accurate cumulative, per-turn, context-used, and context-remaining metrics.
4. Traceable local credit usage from a versioned model-rate table.
5. Configurable output formatting and model-rate overrides.
6. Automated unit and integration tests.
7. Local installation, upgrade, removal, and hook-trust instructions.
8. Architecture, compatibility, privacy, and troubleshooting documentation.
9. A changelog and versioned release artifact.

## Acceptance Criteria for the First Stable Release

- A supported Codex client displays one usage report after every normal completed turn.
- A tool-heavy turn reports the complete turn delta rather than only the last model call.
- Cumulative token values match Codex's structured usage values.
- Context remaining matches the latest known context window and input-token values.
- Credit calculations distinguish input, cached input, and output rates.
- Unknown models never silently reuse another model's rate.
- Missing usage data does not break or prolong a Codex turn.
- No prompt, response, transcript, credential, or account token is transmitted to a third party.
- Installation and removal are documented and reproducible on supported platforms.

## Current Status

Alpha implementation. The transcript adapter, baseline fallback, local credit accounting, formatter, process-safe state store, interruption/resume handling, plugin manifest, hook configuration, runtime resolver, CI, and automated tests are implemented. The current local quality gate passes with 23 tests and at least 85% branch-aware coverage.

Before the first stable release, the project still needs a reproducible installation/reinstallation helper, incremental credit aggregation for large transcripts, and manual lifecycle/rendering verification in both Codex CLI and Codex Desktop.
