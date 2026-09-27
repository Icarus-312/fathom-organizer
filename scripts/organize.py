#!/usr/bin/env python3
"""Step 5. Build the filing tree locally (staging) from the manifest. Rebuilt from scratch every run.
Clients/<Name>/<Y>/<M>/<date>/   Sales/<Y>/<M>/<date>/<Won|Lost|Follow-up>/   _Internal/...   _Unmatched/...
"""
import re, shutil
from common import *

a, P = cli("Build local tree", ("--min-confidence", dict(type=float, default=0.6)))
by_id = {str(m["recording_id"]): m for m in load_json(P.cache / "meetings.json", [])}
M = Manifest(P)
tree = P.out / "tree"
shutil.rmtree(tree, ignore_errors=True)
OUTCOME = {"won": "Won", "lost": "Lost", "follow_up": "Follow-up"}


def safe(s, n=110):
    return re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "-", (s or "untitled")).strip(" .-")[:n] or "untitled"


def route(r):
    y, mo, d = r["date"][:4], r["date"][5:7], r["date"]
    dated = f"{y}/{mo}/{d}"
    t = r.get("call_type")
    if r.get("confidence", 0) < a.min_confidence or t == "other":
        return f"_Unmatched/{dated}", safe(r["title"])
    if t in ("internal", "group"):
        return f"_Internal/{dated}", safe(r["title"])
    if t == "sales" and (r.get("sales") or {}).get("outcome") in OUTCOME:
        s = r["sales"]
        return f"Sales/{dated}/{OUTCOME[s['outcome']]}", f"{safe(s.get('prospect') or r.get('counterparty'), 40)} - {safe(r['title'], 60)}"
    if t == "fulfillment" and r.get("client"):
        return f"Clients/{safe(r['client'], 60)}/{dated}", safe(r["title"])
    return f"_Unmatched/{dated}", safe(r["title"])


def body(r, m):
    L = [f"# {r['title']}", "", f"- Date: {r['date']}", f"- Type: {r['call_type']}", f"- Fathom: {r['url']}"]
    if r.get("client"):
        L.append(f"- Client: {r['client']}")
    f = r.get("fulfillment")
    if f:
        L.append(f"- Topic: {f.get('topic')}")
    s = r.get("sales")
    if s:
        L += [f"- Prospect: {s.get('prospect')} ({s.get('company')})", f"- Outcome: **{s.get('outcome')}**",
              f"- Evidence: \"{s.get('outcome_evidence')}\"", f"- Next step: {s.get('next_step')}"]
        if r.get("became_client"):
            L.append(f"- Became client: Clients/{r['became_client']}")
        if s.get("objections"):
            L += ["", "## Objections"] + [f"- **{o['objection']}** ({'overcame' if o.get('overcome') else 'NOT overcome'}): \"{o.get('quote')}\"" for o in s["objections"]]
    summ = ((m.get("default_summary") or {}).get("markdown_formatted") or "").strip()
    if summ:
        L += ["", "## Fathom summary", summ]
    L += ["", "## Transcript"] + [f"[{x.get('timestamp')}] {x['speaker']['display_name']}: {x['text']}" for x in m["transcript"]]
    return "\n".join(L) + "\n"


n = 0
for rid, r in M.data.items():
    if r.get("no_transcript") or rid not in by_id or "call_type" not in r:
        continue
    folder, name = route(r)
    if r.get("offer"):  # multi-offer profile: offer is the top-level folder
        folder = f"{safe(r['offer'], 60)}/{folder}"
    p = tree / folder
    p.mkdir(parents=True, exist_ok=True)
    fn = f"{name}.md"
    if (p / fn).exists():
        fn = f"{name} ({rid}).md"
    (p / fn).write_text(body(r, by_id[rid]))
    M.update(rid, path=f"{folder}/{fn}")
    n += 1
M.save()
print(f"{n} files -> {tree}")
