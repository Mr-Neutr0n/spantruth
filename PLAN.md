# spantruth plan: year one

Written 2026-11-03, for November 2026 to October 2027. This is the project-level plan. Feature plans
are in [`.plans/`](.plans/), and the research behind this plan is in
[`.context/CONTEXT_llm_telemetry_testing_landscape.md`](.context/CONTEXT_llm_telemetry_testing_landscape.md).

## The goal

spantruth is the default answer to one question: does this LLM telemetry report the numbers that the
provider sent?

Two groups decide whether that is true:

- **Maintainers of instrumentation libraries.** They run spantruth on every pull request, against their
  own checkout, with their known failures recorded in their own repository.
- **Engineers who choose or trust a library.** They read the report before they rely on a cost
  dashboard, a token budget or an alert.

## Where the project stands

Measured on 2026-11-03.

| Area | State |
| --- | --- |
| Release | v0.2.0 is tagged. Its PyPI job failed with `Trusted publishing exchange failure`, so `spantruth` is not on PyPI and the name is unclaimed. |
| Install | spantruth runs only from a clone, because the subjects are not in the wheel. |
| Coverage | 32 scenarios: OpenAI Chat Completions, Anthropic Messages, and one OpenAI Responses API scenario. Three libraries and two controls. |
| Nightly report | Green. At the latest releases, OpenInference and the OpenTelemetry GenAI instrumentation pass 32 of 32 cells. OpenLLMetry fails 13 of 32. |
| Upstream | OpenInference fixed both early-exit findings (openai 0.1.66, anthropic 3.1.0). Three OpenLLMetry items are open. The OpenLLMetry finding that the README calls "not reported yet" is now openllmetry#4643. |
| SDKs | Subjects run openai 3.28.0 and anthropic 1.13.0. The current versions are 3.42.1 and 2.4.0. `--latest` moves the library, never the SDK. |
| CI use | `spantruth run` exits 0 when a subject environment fails to build, so a CI job cannot see the failure. |
| Contributors | Five pull requests are open. Three are from first-time contributors: Logfire (#14), OpenLIT (#15) and a retried 429 (#16). The oldest has waited 7 days. |
| Mentions | Listed in awesome-python-testing. No mention yet in the repositories of the libraries that it tests. |

The core is strong, and it stays: values instead of presence, fixtures checked with the SDK's own
types, reads under every naming convention, the app-unchanged check, the lost-span probe, the two
controls, a rule permalink on every check, and a public dispute path.

## Prior art

As of 2026-11-03. Details and sources are in the context file.

| Project | What it checks | How spantruth differs |
| --- | --- | --- |
| OpenTelemetry `semantic-conventions-genai/reference`, with the conformance runner and Weaver | Names and types that hand-written reference instrumentations of about 40 client SDKs emit against a mock server | spantruth tests the packages that people install, compares values with the wire, and drives the failure paths |
| Weaver live-check | Received telemetry against the semantic-convention registry | Conformance to the registry, not to the provider's numbers |
| pytest-genai-semconv | Presence and types on your own spans, in unit tests | No fake provider, no real SDK, no failure paths |
| kartsan03/wiretruth | What the provider SDK returns to the caller | spantruth checks what the instrumentation writes on the span, and it replays wiretruth fixtures |
| Bowtie (JSON Schema) | Every implementation against one suite, with a report site, badges, a setup action and a job summary | A different domain. It is the model for how a harness for many implementations grows. |

What spantruth takes from Bowtie, test262 and web-platform-tests: a one-step CI path, a job summary, a
badge per implementation, known failures recorded in the implementer's repository with an issue link,
and test IDs that never change meaning.

Use something else when you need name and type conformance across the whole registry (Weaver
live-check), when you test your own spans in unit tests (pytest-genai-semconv), or when you test what
the SDK returns (wiretruth).

## Strategy

Five bets. Every epic below serves at least one of them.

1. **Run where maintainers work.** One step in their CI, against their checkout, with their known
   failures. Without it, maintainers read the report but do not use spantruth.
2. **Cover what people install.** Libraries follow usage. Providers follow SDK downloads: openai 296M a
   month, anthropic 150M, google-genai 138M (pypistats, 2026-11-03).
3. **Target the bug classes that repeat.** Twenty issues in six months, in eight independent projects,
   fall into four classes: cache tokens dropped or counted twice, reasoning tokens dropped, spans that
   never end, and one call reported on two spans. Each new scenario targets a class with a public
   instance.
4. **Never be wrong in public.** Every new check gets a rule with a permalink and a planted fault in
   `control-faulty`. One unfair red cell costs more trust than ten findings earn.
5. **Send every finding upstream, with a link back.** The upstream issue is how maintainers find
   spantruth. It needs a permalink to the finding and a command that reproduces it.

## Non-goals for year one

- No ranking and no total score. [GOVERNANCE.md](GOVERNANCE.md) says so.
- No hosted service, and no data collected from users.
- No cost checks. They need a price table, which is opinion and goes stale.
- No checks of backends such as Langfuse or Datadog. spantruth grades what a library exports.
- No calls to real providers.
- No Windows runner. Subject environments use the POSIX layout.

## Epics

Each epic says why it exists and how we know that it is done.

### E0. Maintainer hygiene (now)

Why: five pull requests wait, and the package name is unclaimed. Both cost more every day.

- Create the PyPI trusted publisher for workflow `release.yml` and environment `pypi`, then publish the
  next tag. The wiretruth name went to another project 26 hours after the launch.
- Review #14 (Logfire), #15 (OpenLIT) and #16 (retried 429) within days, and merge when they are
  ready. Write the review against the PR checklist: every red cell traced to a line of code.
- Merge the Dependabot pull requests #17 and #18 after CI passes.

Done when `pip install spantruth` works and no contributor waits more than three days for a first
review.

### E1. Run it anywhere

Why: bet 1. A maintainer must not have to clone spantruth to test a library.

- `uvx spantruth run` works with no clone.
- `--subject ./dir` runs a subject that lives in the maintainer's repository.
- `--with ./packages/x` tests a local checkout.
- Exit codes that a CI job can trust. `--expect` compares the run with recorded known failures, and
  `--write-expect` records them.
- A GitHub Action, `Plexito-de/spantruth@<tag>`, with a job summary and the reports as an artifact.
- Current SDKs: the base SDK pins move to current versions, and `--latest` moves them too.

Done when a workflow of about ten lines tests a checkout and fails on a regression, and CI proves the
action on both controls. Feature plan: [PLAN_FEAT_run-anywhere.md](.plans/PLAN_FEAT_run-anywhere.md).

### E2. A report that people link to

Why: bet 5.

- First half: a permalink for every finding, matrix cells that link to their finding, the command that
  reproduces it, the spans the library exported, and a schema version in the results document.
- Second half, in this order: dated snapshots of each nightly report, so that a permalink in an
  upstream issue still resolves after the fix lands; a "changed since the last run" section (fixed and
  regressed); a preview card for shared links.

### E3. The bug classes that repeat

Why: bets 2 and 3. Each scenario names its public instance.

| Scenario | Bug class and public instance |
| --- | --- |
| Usage without the details objects, as OpenAI-compatible servers send it | Cache tokens dropped: openllmetry#4583 |
| Reasoning tokens in a stream | Reasoning dropped on streams: openllmetry#4660 |
| Tool calls in a stream: OpenAI deltas, Anthropic `input_json_delta` | Finish reason lost, or the app breaks |
| SDK helpers: `messages.stream()`, `with_raw_response`, `with_streaming_response` | Nothing recorded: logfire#2549 |
| Anthropic usage that grows in `message_delta` | Final counts ignored: mlflow#26907 |
| The rest of the OpenAI Responses API: plain, stream, cache, reasoning, function call, 429 | openinference#4185, logfire#2565 |
| A 429 that the SDK retries (#16) | Two spans, or an error status on a call that succeeded |
| Two concurrent calls in one trace | Counts that cross between spans |

Start after #16 is merged, because it changes the scenario registry, the fake provider and the model.

### E4. Providers (Q1 and Q2 2027)

- Google Gemini through `google-genai`: `generateContent` and its SSE stream. Gemini reports thought
  tokens apart from candidate tokens, and the output count must include them. This is the Anthropic
  cache rule again, in a new place.
- AWS Bedrock Converse and ConverseStream. The fake provider needs AWS event-stream framing.
- Azure OpenAI. Cheap after the OpenAI APIs are complete.

### E5. Libraries (continuous, about one every two weeks)

Order by reach: Logfire (#14) and OpenLIT (#15) first, then the official google-genai and Bedrock
packages from opentelemetry-python-contrib, Langfuse, MLflow and AgentOps. LiteLLM, Pydantic AI,
Strands and Google ADK need E6.

Rule for every subject: use the setup that its documentation shows first, and trace every red cell to
a line of code before the report shows it.

### E6. Frameworks as subjects (Q2 2027)

Why: LiteLLM has 92M downloads a month, and frameworks such as Pydantic AI, Strands and LangChain emit
the spans themselves. There the app calls the framework, not the SDK.

- A subject can bring its own `app.py`, which makes each call through the framework.
- A subject declares the scenarios that it supports.

### E7. Metrics (Q2 2027)

Why: dashboards often sum metrics, not spans. The GenAI conventions define token counters and
histograms (`gen_ai.client.inference.usage.*`).

- Grade the token metrics against the wire, per call and per token type.
- Give subjects a meter provider. Plant a metric fault in `control-faulty`.

### E8. JavaScript and TypeScript (Q3 2027)

Why: the Vercel AI SDK (`ai`, 118M npm downloads a month), OpenLLMetry-JS and OpenInference-JS.

- A Node driver that speaks the same protocol as the Python driver: a call plan in, an observation out,
  and a lost-span probe.
- First step: write the driver protocol down, and give the driver the scenario as data instead of an
  ID.

### E9. Content capture (only on demand)

The recorded output text equals what the app read, and prompts appear only when the user opts in.

### E10. Community and neutrality (continuous)

- Ask one maintainer team whether a CI gate is what they want, before the action gets more polish.
  OpenInference fixed two findings within two weeks, so it is the first contact.
- Offer each covered library a pull request that adds the action to its CI. We write the first ones.
  The Bowtie author wrote most of its early harnesses himself.
- List the action on GitHub Marketplace. The owner accepts the Marketplace Developer Agreement and
  ticks the box on a release. The name in `action.yml` must be unique there.
- Present spantruth to the OpenTelemetry GenAI SIG as the complement to Weaver and the reference
  scenarios: values and failure paths. Ask for a link from `semantic-conventions-genai/reference`.
- Invite co-maintainers from at least two libraries.
- Keep the stable-ID policy: a scenario ID or a check ID never changes meaning.
- Publish a write-up of the findings in Q4 2026, after Logfire and OpenLIT are on the report. The
  findings exist today, and a later date gives away the cheapest way to get noticed. Tell each
  maintainer before it goes out. A second write-up follows Gemini and the frameworks.

Decisions for the owner, not for this plan:

- CLA or DCO. A CLA adds a step to every first contribution.
- The long-term home: Plexito, or a neutral foundation after maintainers adopt spantruth.

## Calendar

| Quarter | Ships |
| --- | --- |
| Q4 2026 | E0, E1, the first half of E2, Logfire and OpenLIT, the first write-up, the first wave of E3. Releases 0.3 and 0.4. |
| Q1 2027 | Gemini, E6 with LiteLLM and Pydantic AI, the second half of E2, the first maintainer CI adoption, the SIG presentation. |
| Q2 2027 | E8, the Vercel AI SDK first, then OpenLLMetry-JS and OpenInference-JS. |
| Q3 2027 | E7, Bedrock, Azure OpenAI. |
| Q4 2027 | 1.0: a stable results schema, stable IDs, co-maintainers. |

Frameworks and TypeScript come before metrics and Bedrock, because most AI engineers work in a
framework or in TypeScript, and they find spantruth through the tools that they use.

## Measures

Leading measures, checked every month:

| Measure | 2026-11-03 | Target for October 2027 |
| --- | --- | --- |
| Libraries covered | 3 | 12 |
| Providers | 2 | 5 |
| Scenarios | 32 | about 80 |
| Repositories that run the action in CI | 0 | 5 |
| Findings reported upstream | 7 | 40 |
| Findings fixed upstream | 2 | 20 |
| Days to the first review of a contributor pull request | 7 | 3 at most |

Lagging measures: GitHub stars, PyPI downloads, pull requests from library maintainers, and links from
OpenTelemetry documentation.

## Risks

| Risk | Mitigation |
| --- | --- |
| An unfair red cell | Rule permalinks, the controls, the dispute path, and every red cell traced to code before publication |
| Churn in the semantic conventions, where every GenAI attribute is still in development | Reads under every known name, pinned permalinks, and a scheduled check that cited lines still say what the rule quotes |
| SDK churn breaks fixtures | Fixtures parse with the SDK types in the test environment, and the nightly run uses the latest SDKs |
| New scenarios break a maintainer's CI | The action runs the spantruth of its own ref. A maintainer pins a tag and takes new scenarios with a deliberate bump. |
| Overlap with the OpenTelemetry conformance work | Position spantruth as the complement, and offer the value checks upstream |
| One maintainer | Co-maintainers, generated documentation, CONTRIBUTING.md |
| CI minutes stop a maintainer from adopting the action | The action caches the uv cache. Document the cost of a run. |
| A maintainer's CI depends on PyPI and on spantruth's pins | The environment build retries once. The docs say that exit code 3 is not a bug in their library. |
| The version in the wheel, the tag and the results document disagree | One source for the version, and the release job checks it against the tag |

## Decisions in this plan

Each new interface names the alternative that lost. The feature plans hold the rest.

1. **Review the contributor pull requests instead of building the same subjects again.** Logfire,
   OpenLIT and the retried 429 are in flight. Building them again would waste the work and lose the
   contributors.
2. **A subject pins its own SDK versions when the library excludes the base versions.** OpenLIT 1.45.0
   declares `anthropic<1.0.0` and `openai<3.0.0`. Rejected: forcing the base versions with
   `uv pip install --overrides`, as #15 does. That tests a combination the library does not claim to
   support, so a red cell would not be fair.
3. **The subjects stay at the repository root.** Rejected: moving them into `src/spantruth/`. That
   hides the place where people contribute, and it conflicts with #14 and #15.
