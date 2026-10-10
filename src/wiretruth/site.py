"""One self-contained HTML page for a results document. No scripts, no external assets.

Every string from a results document is escaped: attribute values come from the libraries
under test, so they are data, never markup. Colors are paired tokens, one value per scheme.
"""

from __future__ import annotations

from html import escape
from typing import Any

from .report import LEGEND, _subjects, findings

ICON = (
    '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' '
    "viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%231a6b37'/%3E"
    "%3Cpath d='M4 8l3 3 5-6' stroke='white' stroke-width='2' fill='none'/%3E%3C/svg%3E\">"
)
CSS = """
:root{--bg:#fbfbf9;--fg:#1b1d21;--muted:#545b66;--line:#e2e4e8;--card:#fff;
--pass:#1a6b37;--pass-bg:#e5f4ea;--missing:#6b4f00;--missing-bg:#fdf3d6;--wrong:#9a1f27;
--wrong-bg:#fbe5e6;--lost:#55267d;--lost-bg:#efe6f8;--broken:#7f3600;--broken-bg:#fdeadd;
--inc:#3f4853;--inc-bg:#eceef1;--link:#1a56b0}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--fg:#e8eaed;--muted:#a7aeb8;
--line:#2a2e35;--card:#181b20;--pass:#7fd49b;--pass-bg:#173322;--missing:#f1cf6b;
--missing-bg:#3a3014;--wrong:#ff9aa0;--wrong-bg:#3d1a1d;--lost:#cfaaf5;--lost-bg:#2c1e3d;
--broken:#ffb27c;--broken-bg:#3d2414;--inc:#c3c9d1;--inc-bg:#272b31;--link:#8ab4ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;margin:0 0 4px}h2{font-size:19px;margin:40px 0 12px}
p{margin:8px 0;max-width:72ch}a{color:var(--link)}.muted{color:var(--muted)}code{font-size:13px}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%}th,td{padding:8px 10px;
border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{font-size:13px;color:var(--muted);font-weight:600}tbody th{font-weight:400}
tr:last-child td,tr:last-child th{border-bottom:0}td.c{text-align:center;white-space:nowrap}
.v{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600}
.pass{color:var(--pass);background:var(--pass-bg)}
.missing{color:var(--missing);background:var(--missing-bg)}
.wrong{color:var(--wrong);background:var(--wrong-bg)}.lost{color:var(--lost);background:var(--lost-bg)}
.broken{color:var(--broken);background:var(--broken-bg)}
.inconclusive{color:var(--inc);background:var(--inc-bg)}.na{color:var(--muted)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:10px 0 0}
dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}details{border:1px solid var(--line);
border-radius:10px;background:var(--card);padding:10px 14px;margin:8px 0}
summary{cursor:pointer}.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:12px 0}
"""


def _badge(verdict: str) -> str:
    if verdict == "n/a":
        return '<span class="na" title="not graded">·</span>'
    return f'<span class="v {escape(verdict)}">{escape(verdict)}</span>'


def _matrix(doc: dict, names: list[str]) -> str:
    head = "".join(
        f'<th scope="col"><a href="{escape(doc["subjects"][n]["homepage"])}">{escape(n)}</a></th>'
        for n in names
    )
    rows = []
    for sid, sc in doc["scenarios"].items():
        cells = "".join(
            '<td class="c">'
            + _badge(doc["subjects"][n]["cells"].get(sid, {}).get("verdict", "n/a"))
            + "</td>"
            for n in names
        )
        rows.append(
            f'<tr><th scope="row"><code>{escape(sid)}</code><br>'
            f'<span class="muted">{escape(sc["title"])}</span></th>{cells}</tr>'
        )
    return (
        f'<div class="wrap"><table><thead><tr><th scope="col">Scenario</th>{head}</tr>'
        f"</thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _finding(f: dict[str, Any]) -> str:
    rule = escape(f.get("rule", ""))
    if f.get("rule_url"):
        rule = f'<a href="{escape(f["rule_url"])}">{rule}</a>'
    fields = [
        ("Expected", f.get("expected")),
        ("Reported", f.get("got")),
        ("Read from", f.get("where")),
        ("Note", f.get("detail") or None),
    ]
    rows = "".join(
        f"<dt>{k}</dt><dd><code>{escape(str(v))}</code></dd>" for k, v in fields if v is not None
    )
    issue = f.get("issue")
    if issue:
        note = f" {escape(issue['note'])}" if issue.get("note") else ""
        rows += (
            f'<dt>Upstream</dt><dd><a href="{escape(issue["url"])}">'
            f"{escape(issue['status'])}</a>{note}</dd>"
        )
    return (
        f"<details><summary>{_badge(f['verdict'])} {escape(f['subject'])} · "
        f"<code>{escape(f['scenario'])}</code> · {escape(f['id'])}</summary>"
        f"<dl>{rows}<dt>Rule</dt><dd>{rule}</dd></dl></details>"
    )


def _versions(doc: dict, names: list[str]) -> str:
    items = []
    for n in names:
        s = doc["subjects"][n]
        pkgs = ", ".join(f"{k} {v}" for k, v in sorted(s.get("versions", {}).items()))
        err = ""
        if s.get("error"):
            err = f' <span class="v inconclusive">{escape(s["error"][:160])}</span>'
        items.append(
            f"<li><strong>{escape(n)}</strong>: {escape(s['title'])}. "
            f'<span class="muted">{escape(pkgs)}</span>{err}</li>'
        )
    return f"<ul>{''.join(items)}</ul>"


def render(doc: dict) -> str:
    names = _subjects(doc)
    legend = "".join(f"<span>{_badge(k)} {escape(v)}</span>" for k, v in LEGEND.items())
    found = "".join(_finding(f) for f in findings(doc)) or "<p>No findings.</p>"
    meta = (
        f"wiretruth {escape(doc['wiretruth'])} · {escape(doc['mode'])} versions · "
        f"{escape(doc['created'])} · Python {escape(doc['python'])} · "
        f"semantic-conventions-genai <code>{escape(doc['semconv_genai'])}</code>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>wiretruth report</title>
{ICON}
<meta name="description" content="Does LLM telemetry match what the provider sent?
Wire traffic replayed through instrumentation libraries, checked value by value.">
<style>{CSS}</style></head>
<body><main>
<h1>wiretruth</h1>
<p>Does the telemetry an LLM instrumentation library reports match what the provider actually
sent? Each cell replays one provider response through one library and checks every reported value
against the wire.</p>
<p class="muted">{meta} · <a href="https://github.com/Plexito-de/wiretruth">source</a></p>
<p>Pages: <a href="index.html">pinned versions</a> · <a href="latest.html">latest releases</a>.
A fix that ships upstream turns its cell green on the latest-releases page first.</p>
<div class="legend">{legend}</div>
{_matrix(doc, names)}
<p class="muted">The controls run the suite's own reference instrumentation.
<code>control-honest</code> has to pass every check, and <code>control-faulty</code> has to fail
exactly its planted faults. If either moves, the suite is wrong, not a library.</p>
<h2>Findings</h2>
<p class="muted">Every finding cites the rule it applies. To dispute one, open an issue: a disputed
finding is marked as such in <a href="https://github.com/Plexito-de/wiretruth/blob/main/known_issues.toml">known_issues.toml</a>.</p>
{found}
<h2>Subjects and versions</h2>
{_versions(doc, names)}
</main></body></html>
"""
