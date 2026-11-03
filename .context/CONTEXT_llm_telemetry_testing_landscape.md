# The landscape around testing LLM telemetry values

Researched on 2026-11-03. Every number has its source and date. Anything marked "unverified" was not
confirmed at the source. Re-check a number before you quote it in public.

## Prior art

Nothing found on 2026-11-03 does all of these together: a fake provider, the real provider SDK, the
production instrumentation packages, an OTLP receiver, and values compared with what the provider sent,
including failure paths.

| Project | What it checks | Difference from a value check |
| --- | --- | --- |
| [semantic-conventions-genai `reference/`](https://github.com/open-telemetry/semantic-conventions-genai/tree/main/reference) | Hand-written reference instrumentations (built on `opentelemetry-util-genai`) of about 40 client SDKs and frameworks, run against a deterministic mock server. The [conformance runner](https://github.com/open-telemetry/semantic-conventions-conformance) validates the captured telemetry with Weaver and generates a matrix of supported attributes. | The instrumentation is a reference, not the package users install. The checks are names, types and required attributes, not equality with the provider's numbers. |
| [Weaver live-check](https://github.com/open-telemetry/weaver/blob/main/docs/usage.md) | Received OTLP against a semantic-convention registry, with OPA policies. `--fail-on` sets the exit level. `--diagnostic-format gh_workflow_command` writes workflow annotations. | Conformance to the registry, not to the wire. |
| [pytest-genai-semconv](https://github.com/Krishnachaitanyakc/pytest-genai-semconv) (0.1.0, 2026-07-06) | A pytest plugin with in-memory span capture and `assert_chat_span(...)` helpers: presence, types, span kind. | Tests your own spans. No fake provider, no real SDK, no failure paths. |
| [kartsan03/wiretruth](https://github.com/kartsan03/wiretruth) | What the provider SDK returns to the caller, from recorded responses. Owns the `wiretruth` name on PyPI (0.1.0 on 2026-10-11, 0.2.0 on 2026-10-13). | Checks the SDK, not the span. Its fixture format is replayable. |
| [4ktLuffy/spanproof](https://github.com/4ktLuffy/spanproof) | Sentry SDK integrations, with fixtures validated by the provider SDK's types. | One vendor. |
| [arthi-arumugam-git/wrong-numbers](https://github.com/arthi-arumugam-git/wrong-numbers) | A field guide to wrong numbers in eval, tracing and cost libraries. | Documentation, not a harness. |
| [jkelly-dev1/llm-observability-stack](https://github.com/jkelly-dev1/llm-observability-stack) | A personal study. Cost computed from spans was 44% below the provider's usage, because the span copied an `input_tokens` field that excludes the cached prefix. | Not a tool. Evidence for the cache-token class. |

The reference scenarios name their metrics `gen_ai.client.inference.usage.input_tokens` (a counter) and
`gen_ai.client.inference.operation.input_tokens` (a histogram), with matching output, cache and
reasoning names. Source: `reference/scenarios/anthropic/scenario.py` on the `main` branch, 2026-11-03.

## The semantic conventions

- The GenAI conventions moved to their own repository,
  [semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai), in
  semconv v1.42. Every GenAI attribute in its registry has `stability: development`.
- Token attributes: `gen_ai.usage.input_tokens` (SHOULD include cached tokens),
  `gen_ai.usage.output_tokens` (SHOULD include reasoning tokens), `gen_ai.usage.cache_read.input_tokens`,
  `gen_ai.usage.cache_write.input_tokens` and `gen_ai.usage.reasoning.output_tokens`.
- The cache-write attribute was `cache_creation.input_tokens` first. The rename is live, and
  instrumentations lag: [pydantic-ai#11779](https://github.com/pydantic/pydantic-ai/issues/11779)
  (2026-10-28). The date of the rename is unverified.
- Since v1.37.0 (2025-08-25), content goes in `gen_ai.input.messages`, `gen_ai.output.messages` and
  `gen_ai.system_instructions`, or in the `gen_ai.client.inference.operation.details` event.

## Who would run a value check

pypistats "last month" and npm downloads, read on 2026-11-03. Download counts mix SDK use with
instrumentation use, so they rank reach, not need.

| Library | Downloads a month | Emits OTel GenAI spans |
| --- | --- | --- |
| LiteLLM | 92.2M | Through its OTel callback |
| Langfuse SDK | 23.6M | OTel-based SDK |
| MLflow | 19.9M | OTel export |
| Pydantic Logfire | 13.0M | Yes |
| opentelemetry-util-genai (official) | 4.91M | Yes |
| OpenLLMetry anthropic and openai | 3.02M and 2.86M | Yes |
| OpenInference openai and anthropic | 2.25M and 0.78M | Its own `llm.*` names |
| OpenLIT | 278k | Yes |
| Vercel AI SDK (`ai`, npm) | 118.4M | `experimental_telemetry`, mixed names (unverified) |

Provider SDKs: openai 295.9M, anthropic 150.2M, google-genai 137.6M, groq 16.8M and mistralai 16.2M a
month. On npm: `@anthropic-ai/sdk` 181.4M, `openai` 162.0M and `@google/genai` 91.6M.

## Demand: the bug classes repeat

Issues and pull requests created between 2026-05-03 and 2026-11-03, with their state on 2026-11-03.
Four classes repeat across eight independent projects: cache tokens dropped or counted twice, reasoning
tokens dropped, spans that never end, and one call reported on two spans.

- Cache tokens: [openllmetry#4665](https://github.com/traceloop/openllmetry/issues/4665),
  [openllmetry#4583](https://github.com/traceloop/openllmetry/issues/4583) (`prompt_tokens_details` is
  None), [mlflow#26907](https://github.com/mlflow/mlflow/issues/26907) (final counts in `message_delta`
  ignored), [mlflow#26817](https://github.com/mlflow/mlflow/issues/26817),
  [litellm#49558](https://github.com/BerriAI/litellm/pull/49558),
  [langfuse#19483](https://github.com/langfuse/langfuse/pull/19483) and
  [pydantic-ai#11779](https://github.com/pydantic/pydantic-ai/issues/11779).
- Reasoning tokens: [openllmetry#4660](https://github.com/traceloop/openllmetry/issues/4660) (streamed
  chat), [litellm#49557](https://github.com/BerriAI/litellm/pull/49557) and
  [python-contrib#4987](https://github.com/open-telemetry/opentelemetry-python-contrib/pull/4987).
- Spans that never end: [openllmetry#4608](https://github.com/traceloop/openllmetry/issues/4608),
  [openllmetry#4597](https://github.com/traceloop/openllmetry/issues/4597),
  [openllmetry#4650](https://github.com/traceloop/openllmetry/pull/4650) and
  [openinference#4215](https://github.com/Arize-ai/openinference/pull/4215).
- One call on two spans: [openllmetry#4609](https://github.com/traceloop/openllmetry/issues/4609).
- Calls through other entry points record nothing:
  [logfire#2549](https://github.com/pydantic/logfire/issues/2549) (`with_raw_response` and
  `with_streaming_response`).
- Responses API paths: [openinference#4185](https://github.com/Arize-ai/openinference/issues/4185) and
  [logfire#2565](https://github.com/pydantic/logfire/pull/2565).

## How conformance suites became the default

From primary sources, read on 2026-11-03.

- **[Bowtie](https://github.com/bowtie-json-schema/bowtie)** is the closest model. Each JSON Schema
  implementation runs in a container with a small harness that speaks a JSON-lines protocol on stdin and
  stdout. Harnesses live in the implementers' directories. Bowtie has a report site, shields.io endpoint
  badges, a composite setup action that installs it with uv, and `bowtie summary --format markdown` for
  the job summary. A skipped test carries an issue URL. Its author wrote most early harnesses himself.
  It launched with 12 implementations and now has 24.
- **test262** and **web-platform-tests** keep known failures in the implementer's repository and
  publish results per implementation (test262.fyi, wpt.fyi).
- **Kubernetes conformance** gives a trademark to certified products, and the trademark drives
  adoption.
- **Protocol Buffers conformance** uses a small "testee" per language over stdin and stdout, the same
  idea as the Bowtie harness.

Patterns that drove adoption: a tiny harness as the unit of contribution, the harness in the
implementer's repository, a public result and a badge per implementation, known failures recorded with
an issue link, a one-step CI path, a neutral home, and a funded maintainer who writes the first
harnesses.

Weaknesses seen: a frozen toolchain (Autobahn is pinned to Python 2), no stable test identity (Bowtie
matches skips by description), governance that never became formal, and no documented dispute path.

Launch posts alone rarely drove adoption: the promptfoo Show HN scored 14 points. Integrations in the
places users already work mattered more.

## Related Context

None yet.
