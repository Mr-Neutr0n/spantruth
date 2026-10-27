# Contributing to spantruth

Thank you for your interest. spantruth gets better with every library, provider and failure mode
that somebody adds, and with every maintainer who tells us where a check is unfair.

## Ways to help

These are the contributions the project needs most. Each one has an issue with the
[`help wanted`](https://github.com/Plexito-de/spantruth/labels/help%20wanted) label.

- **Add a subject.** OpenLIT, MLflow, LiteLLM, and the JavaScript libraries
  (OpenLLMetry JS, OpenInference JS, the Vercel AI SDK) are not covered yet.
- **Add a provider.** AWS Bedrock, Google Gemini and the OpenAI Responses API come next.
- **Add a scenario.** Retries, Anthropic thinking tokens, and tool calls in a stream.
- **Maintain an instrumentation library?** Review the adapter for your library in
  `subjects/<name>/instrument.py`. If it does not use your documented setup, the results are not
  fair, and we want to know.
- **Dispute a finding.** Open an issue with the **Dispute a finding** form. If the rule we cite
  does not say what we claim, we fix the check. If the spec is unclear, we mark the cell as
  disputed in `known_issues.toml` and link the discussion.

## Set up

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or later.

```sh
git clone https://github.com/Plexito-de/spantruth.git
cd spantruth
uv sync
uv run pytest -m "not slow"     # unit tests, about 5 seconds
uv run pytest -m slow           # both controls end to end, about 2 minutes
uv run ruff check . && uv run ruff format --check .
```

`uvx pre-commit install` runs the linters on every commit.

## Add a subject

1. Create `subjects/<name>/subject.toml` with `title`, `homepage`, `providers`, the pinned
   `packages`, and the package names to `track` in the nightly run of the latest versions.
2. Create `subjects/<name>/instrument.py` with one function:

   ```python
   def instrument(tracer_provider, otlp_endpoint):
       # The library's documented quickstart, pointed at tracer_provider or otlp_endpoint.
       return None
   ```

   Use the setup that the library's own documentation shows first. Return nothing, or a list of
   extra tracer providers to flush when the library makes its own.
3. Run it: `uv run spantruth run --subject <name>`.
4. Read every red cell before you open the pull request. A red cell is a claim about somebody's
   library. Find the line of code that causes it, or tell us in the pull request that you could
   not.

## Add a scenario

1. Build the response in `src/spantruth/scenarios.py` with the builders in `wire_openai.py` or
   `wire_anthropic.py`. Give every token count a value that no other count in the scenario has.
2. If the scenario needs a new kind of call, add it to `src/spantruth/calls.py`.
3. Run `uv run pytest`. `test_fixtures_parse_with_sdk_types` proves that the provider's SDK
   accepts your fixture.
4. Run the controls. `control-honest` must pass the new scenario. If it does not, fix the
   reference instrumentation or the check, never the expected result.

## Pull requests

- One topic per pull request. Write the title as a
  [Conventional Commit](https://www.conventionalcommits.org/): `feat(subjects): add logfire`.
- Add a test with every change in behavior. A test must fail when you revert the change.
- Update `CHANGELOG.md` under **Unreleased**.

## Contributor License Agreement

Before we can merge your first pull request, you sign the
[Plexito Contributor License Agreement](https://github.com/Plexito-de/.github/blob/main/cla/INDIVIDUAL.md).
A bot asks you on the pull request, and you sign with one comment. It is a license, not a
transfer: you keep the copyright in your work. If you contribute for your employer, your employer
signs the [Entity Agreement](https://github.com/Plexito-de/.github/blob/main/cla/ENTITY.md) first.

## Code of Conduct

This project follows the
[Plexito Code of Conduct](https://github.com/Plexito-de/.github/blob/main/CODE_OF_CONDUCT.md).
Report unacceptable behavior to [info@plexito.de](mailto:info@plexito.de).
