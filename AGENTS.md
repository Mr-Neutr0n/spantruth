# Notes for coding agents

Read [CONTRIBUTING.md](CONTRIBUTING.md) first. It applies to you too.

- Run `uv run pytest -m "not slow"` after every change, and `uv run pytest -m slow` before you
  open a pull request. The slow tests run both controls end to end.
- Never edit `subjects/control-faulty/expected.toml` to make a test pass. If a control moves, the
  harness or a check is wrong. Find which one.
- Never change a fixture value to make a library pass. Fixtures follow the provider's wire format,
  and `test_fixtures_parse_with_sdk_types` proves it.
- A check cites a rule in `src/spantruth/rules.py`. A new check needs a rule with a permalink to
  the sentence it applies.
- Every string from a results document is data. `site.py` escapes all of it. Keep it that way.
- Keep the harness offline. Subject processes get a dead proxy, so a client that honors the proxy
  variables fails fast. A client that ignores them (raw sockets) is not stopped, so check new
  subjects for outbound calls.
- A scenario ID or a check ID never changes meaning. Expectation files in other repositories name
  them, so a new meaning gets a new ID.
- A provider SDK can trace itself: the Anthropic SDK does since 1.14.0. `subjects/_base.toml` turns
  that off for every subject, so a library is graded on its own spans, and `anthropic-sdk` turns it
  back on. Check each SDK bump for the same thing: the controls move when it happens.
- The plan is [PLAN.md](PLAN.md), feature plans are in [`.plans/`](.plans/), and the research behind
  them is in [`.context/`](.context/). Update the plan when an epic ships or changes.
