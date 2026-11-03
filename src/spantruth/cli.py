"""spantruth command line: list, run, report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, expectations, paths, report, runner, scenarios, subjects

# GitHub caps a step summary at 1 MiB. Stay below it, and say where the rest is.
SUMMARY_LIMIT = 1_000_000


def _list(_: argparse.Namespace) -> int:
    print("Scenarios:")
    for sid, sc in scenarios.SCENARIOS.items():
        print(f"  {sid:38} {sc.title}")
    print(f"\nSubjects, from {subjects.SUBJECTS}:")
    for name in subjects.all_names():
        s = subjects.load(name)
        print(f"  {name:38} {s.title} ({', '.join(s.providers)})")
    return 0


def _usage(message: object) -> int:
    print(f"spantruth: {message}", file=sys.stderr)
    return 2


def exit_code(doc: dict, differences: list[expectations.Difference]) -> int:
    """3 when the harness could not run something, else 1 on a difference from the expectations."""
    if runner.incomplete(doc):
        return 3
    return 1 if differences else 0


def _append_summary(path: Path, text: str) -> None:
    if len(text.encode()) > SUMMARY_LIMIT:
        text = text.encode()[:SUMMARY_LIMIT].decode(errors="ignore")
        text += "\n\n... cut at 1,000,000 bytes. The results file has everything.\n"
    with path.open("a") as f:
        f.write(text + "\n")


def _run(args: argparse.Namespace) -> int:
    try:
        selected = [subjects.load(ref) for ref in args.subject or subjects.all_names()]
        overrides = tuple(subjects.resolve_override(spec) for spec in args.overrides or ())
        ids = args.scenario or list(scenarios.SCENARIOS)
        for sid in ids:
            scenarios.get(sid)
    except subjects.SubjectError as exc:
        return _usage(exc)
    except KeyError as exc:
        return _usage(exc.args[0])
    if (args.expect or args.write_expect) and len(selected) != 1:
        return _usage("--expect and --write-expect take exactly one --subject")
    try:
        expected = expectations.load(Path(args.expect)) if args.expect else None
    except expectations.ExpectationError as exc:
        return _usage(exc)
    names = [s.name for s in selected]
    if twice := sorted({n for n in names if names.count(n) > 1}):
        return _usage(f"two subjects named {', '.join(twice)}: rename one of the directories")
    installed = {
        subjects.package_name(r) for s in selected for r in subjects.requirements(s, False)
    }
    for spec in overrides:
        if (name := subjects.package_name(spec)) not in installed:
            return _usage(f"--with {spec}: no selected subject installs {name}")
    ids = scenarios.with_dependencies(ids)
    doc = runner.run(
        selected, ids, Path(args.cache), latest=args.latest, jobs=args.jobs, overrides=overrides
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    text = report.markdown(doc)
    differences: list[expectations.Difference] = []
    if args.expect or args.write_expect:
        result = doc["subjects"][selected[0].name]
        found = expectations.failing(result)
    if expected is not None:
        differences = expectations.compare(expected, found, ran=set(result["cells"]))
        text += "\n\n" + expectations.describe(differences)
    print(text)
    print(f"\nwrote {out}")
    if args.write_expect:
        header = (
            f"Known failures of {selected[0].name}, written by spantruth {__version__}.\n"
            "A run with --expect fails when the failing checks differ from this file."
        )
        Path(args.write_expect).write_text(expectations.dumps(found, header))
        print(f"wrote {args.write_expect}")
    if args.summary:
        _append_summary(Path(args.summary), text)
    for gap in runner.incomplete(doc):
        print(f"spantruth: incomplete run: {gap}", file=sys.stderr)
    return exit_code(doc, differences)


def _report(args: argparse.Namespace) -> int:
    doc = json.loads(Path(args.results).read_text())
    if args.html:
        Path(args.html).parent.mkdir(parents=True, exist_ok=True)
        Path(args.html).write_text(report.html(doc))
        print(f"wrote {args.html}")
    if args.badges:
        out = Path(args.badges)
        out.mkdir(parents=True, exist_ok=True)
        for name, badge in report.badges(doc).items():
            (out / f"{name}.json").write_text(json.dumps(badge) + "\n")
        print(f"wrote badges to {out}")
    if args.markdown or not (args.html or args.badges):
        print(report.markdown(doc))
    return 0


def parser() -> argparse.ArgumentParser:
    cache = paths.cache_dir()
    parser = argparse.ArgumentParser(
        prog="spantruth",
        description="Check what LLM instrumentation reports against what the provider sent.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list scenarios and subjects").set_defaults(func=_list)
    run = sub.add_parser("run", help="run subjects against scenarios")
    run.add_argument(
        "--subject",
        action="append",
        help="a built-in subject name, or a subject directory: a path with a slash, such as "
        "./spantruth; repeatable",
    )
    run.add_argument("--scenario", action="append", help="scenario id, repeatable")
    run.add_argument("--latest", action="store_true", help="unpin the subjects' own packages")
    run.add_argument(
        "--with",
        dest="overrides",
        action="append",
        metavar="SPEC",
        help="replace a package with this requirement: a version, a pull request git ref, or a "
        "local checkout (a path with a slash); repeatable",
    )
    run.add_argument(
        "--out",
        default=str(cache / "results" / "latest.json"),
        help="where to write the results document (default: %(default)s)",
    )
    run.add_argument(
        "--cache",
        default=str(cache / "venvs"),
        help="where to keep the subject environments (default: %(default)s)",
    )
    run.add_argument("--jobs", type=int, default=4)
    run.add_argument(
        "--expect",
        metavar="FILE",
        help="compare the failing checks of the one selected subject with this file, and exit 1 "
        "when they differ",
    )
    run.add_argument(
        "--write-expect",
        metavar="FILE",
        help="write the failing checks of the one selected subject to this file",
    )
    run.add_argument(
        "--summary",
        metavar="FILE",
        help="append the Markdown report to this file, such as $GITHUB_STEP_SUMMARY",
    )
    run.set_defaults(func=_run)
    rep = sub.add_parser("report", help="render a results document")
    rep.add_argument("results")
    rep.add_argument("--html", help="write a static HTML report to this path")
    rep.add_argument(
        "--badges", help="write a shields.io endpoint JSON per library to this directory"
    )
    rep.add_argument("--markdown", action="store_true", help="print the Markdown matrix")
    rep.set_defaults(func=_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
