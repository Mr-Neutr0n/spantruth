# wiretruth

**Does your LLM telemetry tell the truth?** wiretruth replays provider responses through LLM
instrumentation libraries and checks the values they report against what the provider actually
sent: tokens, cache tokens, models, finish reasons, errors, and whether the span ends at all.

[![CI](https://github.com/Plexito-de/wiretruth/actions/workflows/ci.yml/badge.svg)](https://github.com/Plexito-de/wiretruth/actions/workflows/ci.yml)
[![Report](https://github.com/Plexito-de/wiretruth/actions/workflows/report.yml/badge.svg)](https://plexito-de.github.io/wiretruth/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)

**[Read the report](https://plexito-de.github.io/wiretruth/)**: every library, every scenario,
every finding with the rule it applies. It is rebuilt every night, at pinned versions and at the
latest releases.

## Why

Cost dashboards, token budgets, alerts and audits all read the numbers that instrumentation
libraries put on spans. When a library adds a count twice or drops a cached token, nothing fails:
the dashboard shows a wrong number with full confidence. When a span never ends, the call is
missing from the trace altogether.

These bugs live on the paths that normal tests skip: a stream the app leaves early, a connection
that drops, a 429, a prompt-cache hit. wiretruth tests exactly those paths, for every library,
in the same way.

## What the first run shows

Pinned versions, 2026-10-10. Every finding but one was already reported upstream, by the people
credited below. wiretruth reproduces each of them on the same footing, and the nightly run against
the latest releases shows when a fix lands.

| Library | Finding | Upstream |
| --- | --- | --- |
| OpenLLMetry | Anthropic streams overcount output tokens. `message_delta` carries the cumulative count, and the wrapper adds it to the count in `message_start` (`1` in the scenarios). | [#4377](https://github.com/traceloop/openllmetry/pull/4377), by @arthi-arumugam-git |
| OpenLLMetry | A sync Anthropic stream that fails mid-way (a dropped connection, an `overloaded_error` event) never ends its span. The async stream ends it with status `ERROR`, but without `error.type`. | not reported yet |
| OpenLLMetry | An OpenAI stream that fails mid-way ends its span with status `OK`, sync and async. | [#4535](https://github.com/traceloop/openllmetry/pull/4535), by @feiiiiii5 |
| OpenLLMetry | An Anthropic stream the app closes early never ends its span. | [#4536](https://github.com/traceloop/openllmetry/issues/4536), by @armanunix |
| OpenInference | A stream the app closes early never ends its span: OpenAI with `close()` or a `with` block, Anthropic with `close()`. | [#3790](https://github.com/Arize-ai/openinference/issues/3790), by @feiiiiii5; [#3930](https://github.com/Arize-ai/openinference/issues/3930), by @armanunix |
| OpenTelemetry GenAI instrumentation | Every scenario passes. | |

Each finding on the report shows the expected value, the reported value, the attribute it was
read from, and the rule it applies, with a link wherever a spec states it.

## How it works

```text
wiretruth run
  ├─ fake provider endpoint     serves the scenario: JSON, SSE stream, 429, dropped connection
  ├─ OTLP/HTTP receiver         collects every span the library exports
  └─ per library: own venv  →  the app calls the real OpenAI / Anthropic SDK
                                    └─ the library under test exports OTLP to the receiver
  checks: wire truth  ×  what the app saw  ×  what the telemetry says  →  verdict per cell
```

- **Values, not presence.** No two token counts in a fixture are equal. A swapped field,
  a dropped cache count, or a sum done twice shows up as a wrong number. For a wrong token count,
  the report names the arithmetic that most likely produced it, such as "cache reads and writes
  left out".
- **Fixtures follow the wire.** The test suite parses every response and every stream event with
  the provider SDK's own types.
- **Convention-neutral.** A value is read under the current OpenTelemetry GenAI names, older names,
  or OpenInference names. A library is never marked wrong for its choice of names.
- **The app is checked too.** Each scenario also runs without instrumentation. If the library
  changes what the app receives (an exception, a chunk, a return value, a hang), the cell is
  `broken`.
- **Spans that never end are found.** An in-process probe records every span start and end. A span
  that never ends is never exported, so the receiver alone could not tell.
- **Offline and deterministic.** No API keys, and no network after install.

## The controls

Two subjects run the suite's own small reference instrumentation. `control-honest` has to pass
every check. `control-faulty` carries four planted faults and has to fail exactly the checks
they target. CI runs both end to end on every change. If either moves, the suite is wrong, not a
library.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| pass | Every graded value matches the wire. |
| missing | The span ended without a value that the wire carried. |
| wrong | A reported value does not match the wire. |
| lost | The span never ended, so no backend ever receives it. |
| broken | The app saw something different from an uninstrumented run. |
| inconclusive | The harness could not run the cell. No verdict on the library. |

## Run it

You need [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Plexito-de/wiretruth.git && cd wiretruth
uv sync
uv run wiretruth list                                    # scenarios and subjects
uv run wiretruth run --subject openllmetry               # one library, every scenario
uv run wiretruth run                                     # everything, about 3 minutes
uv run wiretruth report results/latest.json --html site/index.html
```

Each subject gets its own virtual environment under `.wiretruth/venvs`. `--latest` unpins the
library's own packages. wiretruth runs from a clone, because the subjects live next to the source.
The run behind the table above is committed as
[`results/2026-10-10-pinned.json`](results/2026-10-10-pinned.json).

## Coverage

- **Providers:** OpenAI Chat Completions and Anthropic Messages, sync and async.
- **Scenarios (31):** plain call, stream, stream without usage, prompt-cache hit (plain, streamed,
  and with cumulative counts in `message_delta`), parallel tool calls, reasoning tokens, HTTP 429,
  a stream the app leaves early (by `close()` and by a `with` block), a dropped connection, and
  Anthropic's mid-stream `error` event. Streams and failures run sync and async.
- **Subjects:** the [OpenTelemetry GenAI instrumentation](https://github.com/open-telemetry/opentelemetry-python-genai),
  [OpenLLMetry](https://github.com/traceloop/openllmetry) and
  [OpenInference](https://github.com/Arize-ai/openinference), plus the two controls.

Next: Logfire, OpenLIT, the JavaScript libraries, AWS Bedrock, Gemini and the OpenAI Responses
API. [Help is welcome](CONTRIBUTING.md#ways-to-help).

## Related work

- [open-telemetry/semantic-conventions-conformance](https://github.com/open-telemetry/semantic-conventions-conformance)
  is the official project. It checks which attributes each instrumentation emits, against the
  semantic conventions, with Weaver. wiretruth is complementary: it checks the values, and the
  failure paths. A finding that belongs upstream goes upstream.
- [spanproof](https://github.com/4ktLuffy/spanproof), by 4ktLuffy, applies the same method to
  Sentry's SDK integrations. wiretruth takes its idea of validating every fixture with the
  provider SDK's own types from it.

## Contributing

Contributions are welcome, and so are disputes. If you maintain one of these libraries and a cell
is unfair, [tell us](https://github.com/Plexito-de/wiretruth/issues/new?template=dispute.yml): we
decide every dispute on whether the cited rule says what the check claims. To add a library, a
provider or a scenario, read [CONTRIBUTING.md](CONTRIBUTING.md). First-time contributors sign the
[Plexito CLA](https://github.com/Plexito-de/.github/blob/main/cla/INDIVIDUAL.md) with one comment
on their pull request.

## License

[Apache-2.0](LICENSE). Maintained by [Plexito](https://plexito.de).
