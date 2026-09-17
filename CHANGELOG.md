# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added

- Initial Codex plugin manifest and lifecycle-hook configuration.
- `UserPromptSubmit` baseline capture and `Stop` usage reporting.
- Tolerant Codex JSONL transcript parsing.
- Exact `token_usage_record` turn and thread usage extraction.
- Context-used and context-remaining reporting from token-count events.
- Model-aware local credit calculations with cached-input rates.
- Versioned official fallback rate table and custom rate-table override.
- Atomic session state and duplicate `Stop` suppression.
- Cross-process session locking, concurrent duplicate suppression, and stale-state cleanup.
- Resume, retry, compaction, and interruption-aware pending-state handling.
- Bounded reverse transcript scanning for prompt-time baseline capture.
- POSIX runtime resolution through a plugin environment, system Python, or uv.
- Python 3.11+ package metadata, `uv` lock file, CI, linting, typing, and tests.
