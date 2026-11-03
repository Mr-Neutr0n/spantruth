# Feature plan: run it anywhere

Written 2026-11-03. Parent: [PLAN.md](../PLAN.md), epics E1 and the first half of E2.

## Status

Shipped on 2026-11-03: S1 in #19, S7 in #21, S2 and S3 in #22, S4 in #23, S6 in #24, S5 in #25.
Two plan items changed on contact with the code:

- **The stale-build risk for `--with ./checkout` did not exist.** A test that edits a checkout
  between two runs passed with and without `--refresh-package`, because uv 0.12.19 rebuilds a local
  directory on every install into a cleared environment. The flag was removed and the test stays as
  the guard.
- **The SDK bump moved both controls.** The Anthropic SDK creates its own spans since 1.14.0. The
  fix is `ANTHROPIC_OPEN_TELEMETRY=false` in `subjects/_base.toml` and a new `anthropic-sdk`
  subject, not a change to the controls.

## The problem

A maintainer cannot test a library with spantruth unless they clone spantruth. To test a local
checkout, they must write a PEP 508 file URL by hand. They cannot gate CI on a run either:
`spantruth run` exits 0 when a subject environment fails to build, and there is no way to say "these
failures are known".

## User stories

### S1. Run without a clone

As a library maintainer, I run `uvx spantruth run --subject openllmetry` in any directory.

- From an empty directory, `spantruth list` from an installed wheel shows every subject in `subjects/`
  and every scenario.
- From an empty directory, an installed wheel runs `control-honest` on `openai/basic`, and the cell
  passes.
- The subject process imports the spantruth driver of the running spantruth and nothing else from the
  host environment.
- A clone works as before. `subjects/` and `known_issues.toml` stay at the repository root.

### S2. Bring your own subject

As the maintainer of a library that spantruth does not cover, I keep a subject in my repository and run
`spantruth run --subject ./spantruth`.

- A `--subject` value that contains a `/` is a directory, and the subject takes the directory name. A
  value without a `/` is a built-in subject.
- A missing `subject.toml`, a missing key, or two subjects with one name give one clear error line and
  exit code 2.

### S3. Test my checkout

As a maintainer, `--with ./packages/opentelemetry-instrumentation-anthropic` installs my working copy
in place of the released package.

- The package name comes from `[project].name`, or else from `[tool.poetry].name`.
- The results record the resolved requirement. A directory with no name gives one clear error and exit
  code 2.

### S4. Trust the exit code

As a CI author, I read from the exit code whether the run measured what I asked, and whether it
matches my known failures.

| Code | Meaning |
| --- | --- |
| 0 | Every cell ran. With `--expect`, the failing checks equal the expected ones. |
| 1 | `--expect` is given, and the failing checks differ. The output names every difference. |
| 2 | Usage error. |
| 3 | The run is incomplete: an environment did not build, a baseline failed, or a cell is inconclusive. Code 3 wins over code 1. |

- `--write-expect FILE` writes the failing checks of the one selected subject, in the format of
  `subjects/control-faulty/expected.toml`.
- With a subset of scenarios, `--expect` ignores the expected entries for scenarios that did not run.
- `--summary FILE` appends the Markdown report and the expectation differences to a file, such as
  `$GITHUB_STEP_SUMMARY`.
- The controls test reads its expectations through the same code.
- The nightly report accepts code 3, so a broken upstream release still publishes.

### S5. One step in GitHub Actions

```yaml
- uses: Plexito-de/spantruth@v0.3.0
  with:
    subject: openllmetry
    with: ./packages/opentelemetry-instrumentation-anthropic
    expect: .github/spantruth-expected.toml
```

- The job summary shows the matrix, the findings and the expectation differences.
- The JSON results and the HTML report upload as one artifact, also when the step fails.
- The step fails with the exit code of the run.
- Inputs reach the shell through environment variables only, so there is no template injection.
  zizmor passes.
- CI runs the action three times: on `control-honest`, on `control-faulty` with its expectations, and
  on `control-faulty` with an empty expectation file. The third run must fail.

### S6. A finding that people can link to

As a maintainer who received an upstream issue, I open the link and see the finding, the spans that my
library exported, and the command that reproduces it.

- Every finding has a stable anchor, made from its subject, scenario and check.
- Every matrix cell with a finding links to the first finding of that cell.
- Every finding shows `spantruth run --subject <subject> --scenario <id>` and the exported spans with
  their attributes.
- Every string from a results document is escaped, in HTML and in Markdown table cells.
- A finding about a value that has the right content in the wrong type says so. Example: finish reasons
  recorded as the JSON string `["stop"]` instead of a string array.
- The results document has `"schema": 1`.

### S7. The SDKs that people install today

- `_base.toml` pins openai 3.42.1 and anthropic 2.4.0, and lists both in `track`, so `--latest` moves
  them too.
- A subject package with the name of a base package replaces the base package.
- The committed results file, the README table and `known_issues.toml` match a fresh pinned run.

## Modules

- `subjects.py`: `root()` finds the subjects next to the package in a wheel, or at the repository root
  in a clone. `load(ref)` reads a built-in name or a directory. `resolve_override(spec)` turns a local
  directory into a direct reference. `requirements()` lets a subject package replace a base package.
- `runner.py`: `driver_path()` makes a directory that holds only the `spantruth` package, for
  `PYTHONPATH`. The driver runs with `python -P`, in a temporary working directory. There is no
  editable install.
- `expectations.py`, new: `failing(subject_result)`, `load(path)`, `dumps(failing, header)`,
  `compare(expected, got, ran)` and `describe(differences)`.
- `cli.py`: the exit codes, `--expect`, `--write-expect` and `--summary`. The clone check goes.
- `report.py` and `site.py`: anchors, cell links, the reproduce command, spans, escaping, the schema
  version.
- `checks.py`: the type note for a JSON string.
- `action.yml`, new, at the repository root: the composite action.
- `pyproject.toml`: `force-include` maps `subjects/` and `known_issues.toml` into the wheel.

## Tests

| Test | Behavior it covers |
| --- | --- |
| `test_root_is_the_repository_in_a_clone` | The clone layout resolves to the repository `subjects/` |
| `test_driver_path_holds_only_spantruth` | The `PYTHONPATH` directory has exactly one entry |
| `test_wheel_runs_a_control_without_a_clone` (slow) | Build, install in a fresh venv, run `control-honest` from an empty directory |
| `test_subject_from_a_directory` | A copy of `control-honest` loads under its directory name |
| `test_bad_subject_is_one_error_line` | A missing file, a missing key and a duplicate name |
| `test_local_checkout_becomes_a_direct_reference` | `[project].name` and `[tool.poetry].name` |
| `test_subject_package_replaces_a_base_package` | One requirement per package name |
| `test_expectations_round_trip` | `dumps`, then `load`, returns the same mapping |
| `test_compare_names_new_fixed_and_changed_checks` | Each kind of difference appears once |
| `test_compare_ignores_scenarios_that_did_not_run` | A subset run does not fail on absent scenarios |
| `test_exit_code_is_3_when_a_cell_is_inconclusive` | Code 3 wins over code 1 |
| `test_faulty_control_fails_exactly_its_planted_faults` (slow, exists) | Now through `expectations` |
| `test_finding_anchor_is_stable_and_unique` | Same input, same anchor; no collisions |
| `test_matrix_cell_links_to_its_finding` | A red cell has an `href` to the finding anchor |
| `test_hostile_span_attributes_are_escaped` | Attribute keys and values from a library are data |
| `test_markdown_cell_cannot_break_the_table` | A pipe or a backtick in a value stays inside its cell |
| `test_json_string_finish_reasons_are_named` | The detail says "JSON string" |
| `test_action_script_runs_both_controls` (slow) | The action script with `GITHUB_*` variables set, outside CI |

## Decisions and the alternatives that lost

1. **The subjects stay at the repository root, and the wheel maps them in.** Rejected: moving
   `subjects/` into `src/spantruth/`. That puts the contribution surface three levels down, and it
   conflicts with the open pull requests #14 and #15. The cost: `root()` has two branches, one per
   install layout, and a test covers each branch.
2. **The driver reaches the subject environment through `PYTHONPATH`, which points at a directory that
   holds only the spantruth package.** Rejected: the editable install of the repository, because a
   wheel has no repository. Rejected: installing spantruth from PyPI into each environment, because
   that needs the network, a published version, and the same version as the host.
3. **Known failures are an expectation file with an exact comparison.** Rejected: `--fail-on wrong,lost`,
   because most libraries have findings today. That gate fails on the first day and cannot tell a
   regression from a known bug. Rejected: a comparison with a previous results JSON, because that file
   is large, noisy and hard to review in a pull request.
4. **A `--subject` value with a `/` is a directory.** Rejected: a second flag, `--subject-dir`. That is
   two flags for one concept, and the action would need two inputs. pip uses the same rule for
   requirements.
5. **The action is a composite action that runs `uvx --from "$GITHUB_ACTION_PATH"`.** Rejected: a
   container action, because the pull is slow, it runs on Linux only, and it needs uv and Python anyway.
   Rejected: a reusable workflow, because it cannot be one step in an existing job. With the composite,
   the spantruth version is the action ref, and the action does not depend on PyPI.
6. **An incomplete run exits with code 3.** Rejected: exit 0 with a warning, which is the current
   behavior and hides a dead check in CI.
7. **A subject pins its own SDK versions when it must.** Rejected: `--overrides`, as in #15. See
   [PLAN.md](../PLAN.md), decision 2.

## Blind spots

| Unknown | How it bites | What this plan does |
| --- | --- | --- |
| Composite action inputs in a `run:` script | `${{ inputs.x }}` in a script is template injection | Inputs go through `env:` only, and zizmor checks the action |
| `github.action_path` | It points at the action checkout, not at the caller's repository | `uvx --from` that path. Paths in inputs stay relative to the caller's workspace. |
| Hatch `force-include` and editable installs | The mapping is absent in editable mode | `root()` looks next to the package first, then at the repository |
| `python -m` adds the working directory to `sys.path` | A directory in the maintainer's repository can shadow a package | `python -P` and a temporary working directory |
| A local checkout needs its build backend | `uv pip install` gets the backend from PyPI | The network is allowed at install time. The harness stays offline at run time. |
| TOML written without a dependency | A key with a quote breaks the file | Keys are written as JSON-escaped basic strings, and a round-trip test covers them |
| anthropic 2.x | Exception classes or module paths can move | Run both controls on the bump before anything else |
| Python 3.13 and 3.14 | Users run them, and CI does not test them | Add both to the CI matrix |

## Order of work

1. Packaging and the driver path (S1).
2. The SDK bump and the data refresh (S7). It goes second because every expectation file written before
   the bump would go stale at the bump, and because the controls must pass on anthropic 2.x first.
3. Directory subjects and local checkouts (S2, S3).
4. Exit codes and expectations (S4).
5. Report links (S6).
6. The action and its CI job (S5).
7. Documentation: README, CONTRIBUTING, CHANGELOG.

## Plan review, 2026-11-03

A separate instance reviewed this plan and PLAN.md. Each point is accepted, changed, or deferred here.

Accepted, and part of this feature:

- **Exit code 3 means a harness failure only**: an environment that did not build, a failed baseline,
  or a cell with no observation. When `instrument()` raises, the cell gets the check
  `subject.instrument` with the verdict `inconclusive`. The comparison with an expectation file treats
  it like any other failing check, so a library that crashes at setup is a regression (code 1), not an
  incomplete run.
- **A failing check is any verdict other than `pass` and `n/a`**, `inconclusive` included.
- **A scenario selection brings its dependencies.** The verdict of an early-exit cell depends on the
  full-stream cell of the same provider, so the runner adds that scenario. Without it, a subset run
  would compare `lost` with an expected `missing`.
- **An expectation entry with an unknown scenario, check or verdict is a usage error** (code 2). An
  entry for a known scenario that did not run is ignored.
- **`--expect` and `--write-expect` take exactly one subject** (code 2 otherwise).
- **The caller's uv configuration does not reach a subject environment.** uv runs with `--no-config`,
  in a working directory inside the cache.
- **A local checkout is rebuilt on every run**: `--reinstall-package` and `--refresh-package` for each
  `--with` directory.
- **The default cache and the default results file are in the user cache directory**
  (`$XDG_CACHE_HOME/spantruth`, else `~/.cache/spantruth`), so `uvx spantruth run` writes nothing into
  the caller's checkout.
- **The venv cache key has a layout version**, so no environment with the old editable install is
  reused.
- **`spantruth list` prints the directory that the subjects came from.**
- **The wheel test asserts the layout**: `spantruth/subjects/...` is in the wheel, and nothing is at the
  top level of site-packages except `spantruth`.
- **The environment build retries once**, because a maintainer's CI must not fail on one PyPI hiccup.
- **One source for the version**: hatch reads it from `__init__.py`, and the release job compares it
  with the tag.
- **Action details**: `with` and `scenario` are multiline inputs, the artifact name is an input with a
  per-subject default, the summary is capped below the 1 MiB step-summary limit, the action has an
  `exit-code` output, and setup-uv is pinned and caches the uv cache.
- **Subject notes appear on the report.** A subject that runs older SDKs says why.

Changed:

- **Permalinks.** An anchor on the nightly page stops resolving when the library fixes the finding.
  Dated snapshots fix that, and they are the first item of the second half of E2. Until then, the
  anchor is on the nightly page, and the committed results file is the permanent record.

Deferred, with a home in PLAN.md:

- Two releases (S1 to S4 and S7, then S5 and S6). All stories ship together in this session, so one
  release covers them.
- A CI check that the README table matches a fresh pinned run. The table is written by hand, with
  credits. The committed results file is the checked record.
- Fair grading for a library on an older SDK: grade a field `n/a` when the baseline shows that the SDK
  did not surface it. This belongs to the OpenLIT review (#15), where the first old-SDK subject
  arrives.

Rejected:

- `SPANTRUTH_SUBJECTS` to override the subject directory. A directory subject (S2) covers a subject
  in any location, and `spantruth list` now shows where the built-in subjects come from.
- Moving the force-included data to `spantruth/_data/`. `spantruth/subjects/` is inside the package
  already, so it cannot collide with another distribution.
