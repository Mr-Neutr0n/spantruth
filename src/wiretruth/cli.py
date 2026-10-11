"""wiretruth command line: list, run, report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import report, runner, scenarios, subjects


def _list(_: argparse.Namespace) -> int:
    print("Scenarios:")
    for sid, sc in scenarios.SCENARIOS.items():
        print(f"  {sid:38} {sc.title}")
    print("\nSubjects:")
    for name in subjects.all_names():
        s = subjects.load(name)
        print(f"  {name:38} {s.title} ({', '.join(s.providers)})")
    return 0


def _run(args: argparse.Namespace) -> int:
    names = args.subject or subjects.all_names()
    ids = args.scenario or list(scenarios.SCENARIOS)
    for sid in ids:
        scenarios.get(sid)
    overrides = tuple(args.overrides or ())
    installed = {
        subjects.package_name(r)
        for n in names
        for r in subjects.requirements(subjects.load(n), False)
    }
    for spec in overrides:
        if subjects.package_name(spec) not in installed:
            name = subjects.package_name(spec)
            print(f"--with {spec}: no selected subject installs {name}", file=sys.stderr)
            return 2
    doc = runner.run(
        names, ids, Path(args.cache), latest=args.latest, jobs=args.jobs, overrides=overrides
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(report.markdown(doc))
    print(f"\nwrote {out}")
    return 0


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiretruth",
        description="Check what LLM instrumentation reports against what the provider sent.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list scenarios and subjects").set_defaults(func=_list)
    run = sub.add_parser("run", help="run subjects against scenarios")
    run.add_argument("--subject", action="append", help="subject name, repeatable")
    run.add_argument("--scenario", action="append", help="scenario id, repeatable")
    run.add_argument("--latest", action="store_true", help="unpin the subjects' own packages")
    run.add_argument(
        "--with",
        dest="overrides",
        action="append",
        metavar="SPEC",
        help="replace a package with this requirement, such as a pull request git ref; repeatable",
    )
    run.add_argument("--out", default="results/latest.json")
    run.add_argument("--cache", default=".wiretruth/venvs")
    run.add_argument("--jobs", type=int, default=4)
    run.set_defaults(func=_run)
    rep = sub.add_parser("report", help="render a results document")
    rep.add_argument("results")
    rep.add_argument("--html", help="write a static HTML report to this path")
    rep.add_argument(
        "--badges", help="write a shields.io endpoint JSON per library to this directory"
    )
    rep.add_argument("--markdown", action="store_true", help="print the Markdown matrix")
    rep.set_defaults(func=_report)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
