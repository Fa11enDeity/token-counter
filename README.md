# Token Counter for Codex

Token Counter for Codex is a planned Codex lifecycle-hook plugin that reports token usage, context-window usage, and model-adjusted credit consumption after every completed Codex turn.

This repository currently contains project planning only. No runtime dependencies or implementation code have been added yet.

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
Total:   128,420 tokens | 18.73 credits
Turn:     12,806 tokens |  2.14 credits
Context:  81,390 / 272,000 tokens
Remain:  190,610 tokens | 70.1%
Model:   gpt-5.6-sol | high | standard
```

The exact presentation may change during implementation as Codex CLI and Desktop rendering behavior is verified.

## Product Boundaries

The project distinguishes between two different concepts:

- **Raw token usage:** measurable input, cached-input, output, and reasoning-output token counts reported by Codex.
- **Credits:** usage calculated from the active model's credit rate, or preferably obtained from Codex's server-side thread usage estimate.

ChatGPT Plus and Pro included-usage limits are not a fixed token-to-credit conversion. Model selection, context size, reasoning, tool calls, caching, task duration, and service configuration can all affect those limits. The plugin will therefore display server-reported rate-limit windows when available instead of presenting a locally inferred value as exact.

## Implementation Strategy

### 1. Package the feature as a Codex plugin

The project will use a Codex plugin manifest and plugin-bundled lifecycle hooks. The initial hook configuration will register:

- `UserPromptSubmit` to capture the cumulative-usage baseline before a turn starts.
- `Stop` to collect the final counters, calculate the turn delta, and display the report when Codex is about to finish the turn.

Plugin packaging keeps the hook installable across projects while still allowing project-local development and testing.

### 2. Use cumulative deltas for per-turn usage

A single user turn can contain multiple model requests because Codex may reason, invoke tools, process results, and call the model again. The last model request alone is therefore not the complete turn cost.

Per-turn usage will be calculated as:

```text
turn usage = cumulative usage at Stop - cumulative usage at UserPromptSubmit
```

State will be keyed by Codex session and turn identifiers and written atomically to the plugin data directory.

### 3. Prefer structured Codex usage data

The implementation will use the most stable available data source in this order:

1. Codex App Server token-usage and thread-usage data, when accessible to the hook.
2. Version-tolerant parsing of the transcript referenced by the official hook payload.
3. A graceful partial report when a field is unavailable.

Codex currently exposes structured usage containing cumulative and latest token breakdowns plus the model context window. Transcript parsing will be isolated behind an adapter because the official documentation does not promise a stable transcript format.

### 4. Calculate context usage correctly

The latest request's input-token count will be treated as the active context size. Remaining context will be calculated as:

```text
remaining context = model context window - latest input tokens
```

Values will be clamped at zero and clearly marked unavailable if the model context window is not reported. Compaction and model-switch events will cause the calculation to use the newest available values.

### 5. Prefer server-estimated credits, with a local fallback

When Codex provides a thread-level estimated credit value, the plugin will treat it as authoritative. This lets Codex account for the model, reasoning effort, speed tier, and current billing route.

If that value is unavailable, the plugin will calculate credits from a versioned rate table:

```text
credits =
  non-cached input tokens * input rate
  + cached input tokens * cached-input rate
  + output tokens * output rate
```

Rates are expressed per one million tokens. Reasoning tokens will not be counted twice when they are already included in output tokens. Unknown models will still receive an accurate raw-token report, but their credit value will be shown as unavailable until a rate is configured.

### 6. Display without polluting the model context

The `Stop` hook will return the smallest Codex-supported UI/event message that reliably appears after a response. The implementation will avoid returning large model-visible context. CLI, Desktop, and non-interactive behavior will be tested separately because their rendering surfaces are not identical.

### 7. Keep processing local and privacy-preserving

The default implementation will not send prompts, replies, or transcripts to third-party services. It will read only the minimum local metadata needed for usage accounting. Optional Codex account queries will use the existing Codex authentication path rather than collecting or storing credentials.

## Planned Development Environment

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

These tools are planned but have not been installed or configured yet.

## Planned Repository Structure

```text
token-counter/
|-- .codex-plugin/
|   `-- plugin.json                 # Codex plugin manifest
|-- hooks/
|   `-- hooks.json                  # UserPromptSubmit and Stop hooks
|-- src/
|   `-- token_counter/
|       |-- __init__.py
|       |-- cli.py                  # Hook process entry point
|       |-- hook_input.py           # Hook payload validation
|       |-- transcript.py           # Version-tolerant usage extraction
|       |-- app_server.py           # Optional Codex App Server adapter
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

The exact structure may be adjusted if the first App Server integration spike shows that a small compiled helper is required. Such a change will be documented before implementation expands.

## Configuration Goals

Planned user configuration includes:

- Enable or disable raw-token, credit, context, and rate-limit lines.
- Select compact or expanded output.
- Choose exact numbers, abbreviated numbers, or both.
- Include or exclude subagent usage where Codex exposes enough metadata.
- Override or add model credit rates.
- Choose whether server-estimated credits or local rates have precedence.
- Configure behavior for unknown models and temporarily missing usage data.
- Enable diagnostic logging without recording prompt or response content.

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
4. Server-estimated credit usage with a documented local-rate fallback.
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

Planning and repository initialization. Implementation has not started, and no development environment has been installed by this project.

