# Troubleshooting

## No report appears

1. Open `/hooks` in Codex and confirm both Token Counter hooks are discovered, enabled, reviewed, and trusted.
2. Confirm Python 3.11 or newer is available as `python3` on macOS/Linux or through `py -3` on Windows.

On macOS/Linux, the plugin launcher also accepts a plugin-local `.venv` or an uv-managed Python. It checks `uv` on `PATH` and at the official installer's default `~/.local/bin/uv` location.
3. Confirm the hook payload contains a readable `transcript_path`.
4. Run the repository verifier with `uv run python scripts/verify-plugin.py`.

The hook deliberately exits successfully on errors so it cannot prevent Codex from completing a turn.

## Credits show `n/a`

Token Counter requires an exact model and speed-tier entry. Check `config/model_rates.json`, or set `TOKEN_COUNTER_RATES_PATH` to a complete replacement table. The tool does not guess rates for unknown models.

## Token values look much larger than the visible conversation

Cumulative usage counts every model request. Agentic turns may call the model multiple times after tool results, and repeated context is billed again even when much of it is cached. Current context size is shown separately from cumulative consumption.

## Context window differs from a model's advertised maximum

Token Counter displays the effective context window reported by Codex. It may reserve capacity or otherwise differ from a headline model maximum.

## Development commands cannot find `uv`

The official installer normally places `uv` in `~/.local/bin`. Add that directory to the interactive shell `PATH`, restart the terminal, and verify with `uv --version`.
