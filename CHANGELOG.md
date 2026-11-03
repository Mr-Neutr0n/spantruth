# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- A recorded response can be replayed as a scenario, from a fixture in kartsan03/wiretruth's
  `wiretruth.fixture/v1` format. The first is `openai/responses-stream-missing-finish-abort`, the
  first OpenAI Responses API scenario: eight recorded events, then the connection drops.
- The reference instrumentation covers the Responses API, so both controls grade it.
- spantruth runs without a clone. The wheel carries the subjects and the known issues, so
  `uvx --from git+https://github.com/Plexito-de/spantruth spantruth run` works in any directory.
- `spantruth list` names the directory that the subjects come from.
- `anthropic-sdk`, a subject for the Anthropic SDK's built-in tracing, which is on by default since
  anthropic 1.14.0. Its spans get the tokens, the cache counts and the errors right, and record the
  stop reason as `anthropic.message.stop_reason` instead of `gen_ai.response.finish_reasons`.
- `subjects/_base.toml` can set environment variables for every subject (`[env]`). A subject
  package replaces the base package of the same name, for a library that cannot run the base SDK
  versions.
- `--subject ./path` runs a subject from any directory, such as the repository of the library it
  tests. The subject takes the name of its directory.
- `--with ./path` installs a local checkout in place of a released package. The package name comes
  from the checkout's `pyproject.toml`.
- A subject that cannot load, an unknown scenario, or two subjects with one name is one error line
  and exit code 2, not a traceback.
- `--expect FILE` compares the failing checks of one subject with a file of known failures, in the
  format of `subjects/control-faulty/expected.toml`, and exits 1 on any difference. `--write-expect
  FILE` records them. The controls test compares with the same code.
- `--summary FILE` appends the Markdown report and the differences to a file, such as
  `$GITHUB_STEP_SUMMARY`.
- Every finding on the HTML report has its own link, shows its expected and reported values in its
  summary line, the command that reproduces it, and the spans the library exported. A matrix cell
  links to its finding.
- A results document carries `"schema": 1`.

### Changed

- Subjects run openai 3.42.1 and anthropic 2.4.0 (were 3.28.0 and 1.13.0) and opentelemetry-sdk
  1.45.2. OpenInference moves to openai 0.1.69 and anthropic 3.3.0, which fix both of its early-exit
  findings, and the OpenTelemetry GenAI instrumentation to 1.3b0. `--latest` also unpins openai and
  anthropic, so the nightly run of the latest releases runs the SDKs that people install today.
- The Anthropic SDK's own spans are off for the library subjects (`ANTHROPIC_OPEN_TELEMETRY=false`),
  so each library is graded on its own spans. With them on, every library reports each Anthropic
  call on two spans.
- The test environment checks the fixtures with the SDK versions that the subjects run.
- `spantruth run` exits 3 when it could not build an environment, run a baseline, or get an
  observation from a cell. It used to exit 0. The nightly report still publishes on 3.
- When a subject's setup raises, its cells fail the new check `subject.instrument`, with the verdict
  `inconclusive`, so an expectation file can compare it.
- A scenario selection brings the scenarios its verdicts depend on: an early exit runs with its
  full stream.
- Finish reasons recorded as a JSON string instead of a string array are still `wrong`, and the
  finding now says so in words.
- The findings on the HTML report leave out the controls, whose cells CI checks on every change.
- A value from a library cannot break a Markdown table cell any more: pipes and newlines are
  escaped.
- A run writes nothing into the working directory by default. Environments go to
  `~/.cache/spantruth/venvs` and results to `~/.cache/spantruth/results/latest.json`, or under
  `$XDG_CACHE_HOME/spantruth`.
- A subject environment no longer holds an editable install of spantruth. The driver of the running
  spantruth reaches it through `PYTHONPATH`, and it runs with `python -P` in a scratch directory, so
  nothing in the caller's directory can shadow a module.
- uv builds subject environments with `--no-config`, so the caller's `uv.toml` or `[tool.uv]` cannot
  change them. A failed build is retried once.
- The version has one source, `src/spantruth/__init__.py`, and the release job checks that the tag
  matches it.

### Fixed

- The fake provider now drops the connection when `drop_after` equals the number of events, where
  it used to end the stream cleanly.

### Security

- The release workflow uses `pypa/gh-action-pypi-publish` v1.14.3, which fixes
  [GHSA-5xjx-3w67-w9x9](https://github.com/advisories/GHSA-5xjx-3w67-w9x9).

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
