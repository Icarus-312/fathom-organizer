#!/usr/bin/env python3
"""Step 2 (the gate). Read every call in full, decide sales|fulfillment|internal|group|other."""
from collections import defaultdict
from common import *

a, P = cli("Classify each call's type",
           ("--limit", dict(type=int)), ("--workers", dict(type=int, default=6)),
           ("--review", dict(action="store_true", help="just print tallies + samples, no LLM calls")),
           ("--redo", dict(action="store_true", help="forget all types and downstream results, re-classify")))
model = P.get("MODEL_TYPE", "claude-haiku-4-5-20251001")
meetings = sorted(load_json(P.cache / "meetings.json", []), key=lambda m: m["created_at"], reverse=True)
if a.limit:
    meetings = meetings[: a.limit]
M = Manifest(P)
if a.redo:
    for r in M.data.values():
        for k in ("offer", "call_type", "confidence", "counterparty", "reason", "no_transcript", "sales", "fulfillment", "client", "became_client"):
            r.pop(k, None)
OFFERS = [o.strip() for o in P.get("OFFERS", "").split(",") if o.strip()]
sysmsg = system_prompt("type.md", P) + (f"\n\nOFFERS: {json.dumps(OFFERS)}" if OFFERS else "")

for m in meetings:  # register every call so later steps have metadata
    rid = str(m["recording_id"])
    if rid not in M.data:
        inv = m.get("calendar_invitees") or []
        M.update(rid, title=m.get("title"), date=call_date(m, P.tz), url=m.get("share_url"),
                 ext_emails=sorted({i["email"].lower() for i in inv if i.get("is_external") and i.get("email")}),
                 ext_names=sorted({i["name"] for i in inv if i.get("is_external") and i.get("name")}))
    if not m.get("transcript") and "call_type" not in M.data[rid]:
        M.update(rid, call_type="other", confidence=1.0, reason="no transcript", no_transcript=True)

if not a.review:
    todo = [m for m in meetings if "call_type" not in M.data[str(m["recording_id"])]]
    print(f"classifying {len(todo)} calls with {model}")

    def one(m):
        r = llm_json(sysmsg, render(m), model)
        off = r.get("offer", "")
        if OFFERS and off not in OFFERS:
            off = next((o for o in OFFERS if o.lower() == off.lower()), "")
        M.update(m["recording_id"], offer=off, call_type=r["call_type"], confidence=float(r.get("confidence", 0)),
                 counterparty=r.get("counterparty", ""), reason=r.get("reason", ""))
        print(f"  {r['call_type']:<11} {m.get('title')}", flush=True)

    pmap(one, todo, a.workers)
    M.save()

by = defaultdict(list)
for rid, r in M.data.items():
    if "call_type" in r:
        by[r["call_type"]].append(r)
print("\nTYPE TALLY: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(by.items())))
for k, v in sorted(by.items()):
    print(f"\n== {k} ({len(v)}) samples ==")
    for r in v[:10]:
        print(f"  {r['date']} {str(r['title'])[:50]:<50} [{r['confidence']:.2f}] {r['reason']}")
