# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-12

### Changed

- Renamed from wiretruth to spantruth: the package, the command, the module and the repository.
  [kartsan03/wiretruth](https://github.com/kartsan03/wiretruth) is a separate project that checks
  what provider SDKs return to the caller. The cache directory is now `.spantruth/`.
- Each tag now also publishes a wheel to PyPI as `spantruth`. A run still needs a clone, and
  `spantruth list` and `spantruth run` say so when the subjects are missing.

### Added

- `spantruth run --with SPEC` replaces one package of a subject with any pip requirement, such as
  the head of a pull request, and records the commit it resolved to.
- `spantruth report --badges DIR` writes a shields.io endpoint document per library. The nightly
  run publishes them under `badges/` on the report site.

## [0.1.0] - 2026-10-10

### Added

- 31 scenarios for the OpenAI Chat Completions and Anthropic Messages APIs, sync and async: plain
  calls, streams, prompt-cache hits, tool calls, reasoning tokens, HTTP 429, a stream the app
  leaves early (by `close()` and by a `with` block), a dropped connection, and Anthropic's
  mid-stream `error` event.
- A fake provider endpoint and an OTLP/HTTP receiver, both local, both offline.
- Value checks against the wire, convention-neutral across OpenTelemetry GenAI, OpenInference and
  older OpenLLMetry names. Each check cites the rule it applies.
- An in-process probe that finds spans that never end.
- Two controls: a reference instrumentation that passes every check, and the same code with four
  planted faults that fails exactly the checks it targets.
- Subjects: the OpenTelemetry GenAI instrumentation, OpenLLMetry and OpenInference.
- A Markdown and a static HTML report.

[Unreleased]: https://github.com/Plexito-de/spantruth/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Plexito-de/spantruth/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Plexito-de/spantruth/releases/tag/v0.1.0
