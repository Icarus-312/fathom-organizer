#!/usr/bin/env python3
"""Step 6. out/report.md: type tally, sales scoreboard, unbeaten objections in lost deals, calls per client."""
import re
from collections import Counter, defaultdict
from common import *

a, P = cli("Write report.md")
M = Manifest(P)
rows = [r for r in M.data.values() if "call_type" in r]
L = [f"# Call report ({P.name})", "", f"{len(rows)} calls: " + ", ".join(f"{k} {v}" for k, v in Counter(r['call_type'] for r in rows).most_common())]

sales = [r for r in rows if r["call_type"] == "sales" and r.get("sales")]
people = defaultdict(list)  # a prospect's CURRENT status = their latest call
for r in sales:
    people[re.sub(r"[^a-z]", "", (r["sales"].get("prospect") or r["title"]).lower())].append(r)
latest = [sorted(v, key=lambda r: r["date"])[-1] for v in people.values()]
L += ["", f"## Sales: {len(people)} prospects, {len(sales)} calls", "Current status (latest call per prospect): " +
      ", ".join(f"{k} {v}" for k, v in Counter(r['sales']['outcome'] for r in latest).most_common())]
for o in ("won", "lost", "follow_up"):
    L += ["", f"### {o}"]
    for r in sorted((r for r in latest if r["sales"]["outcome"] == o), key=lambda r: r["date"], reverse=True):
        s = r["sales"]
        L.append(f"- {r['date']} **{s.get('prospect')}** ({s.get('company')}): {s.get('one_line')} [call]({r['url']})"
                 + (f" (now client: {r['became_client']})" if r.get("became_client") else "")
                 + f"\n  - \"{s.get('outcome_evidence')}\"")

obj = defaultdict(list)
for r in latest:
    if r["sales"]["outcome"] == "lost":
        for o in r["sales"].get("objections", []):
            if not o.get("overcome"):
                obj[o["objection"].lower().strip()].append((r, o))
L += ["", "## Objections we did not overcome (lost deals)"]
for k, v in sorted(obj.items(), key=lambda kv: -len(kv[1])):
    L += [f"", f"**{k}** x{len(v)}"] + [f"- {r['sales'].get('prospect')}: \"{o.get('quote')}\"" for r, o in v]

cl = defaultdict(list)
for r in rows:
    if r["call_type"] == "fulfillment":
        cl[r.get("client") or "(unresolved)"].append(r)
L += ["", f"## Fulfillment: {len(cl)} clients"]
for c, v in sorted(cl.items()):
    L.append(f"- **{c}**: {len(v)} calls, last {max(r['date'] for r in v)}")
rev = load_json(P.out / "needs_review.json", [])
if rev:
    L += ["", f"## Needs review ({len(rev)}): see needs_review.json / edit aliases.json"]
(P.out / "report.md").write_text("\n".join(L) + "\n")
print(f"wrote {P.out / 'report.md'}")
