# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `wiretruth run --with SPEC` replaces one package of a subject with any pip requirement, such as
  the head of a pull request, and records the commit it resolved to.
- `wiretruth report --badges DIR` writes a shields.io endpoint document per library. The nightly
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

[Unreleased]: https://github.com/Plexito-de/wiretruth/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Plexito-de/wiretruth/releases/tag/v0.1.0
