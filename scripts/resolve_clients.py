#!/usr/bin/env python3
"""Step 4. Turn client/prospect names + emails into ONE canonical client each.
aliases.json is yours to edit (merge people by moving names/emails under one client), then re-run.
Ambiguous calls land in needs_review.json and file under _Unmatched until resolved.
"""
import re
from difflib import SequenceMatcher
from common import *

a, P = cli("Resolve canonical clients")
M = Manifest(P)
apath = P.dir / "aliases.json"
aliases = load_json(apath, {})  # {"Canonical Name": {"names": [normalized...], "emails": [...]}}
MERGE, MAYBE = 0.88, 0.75


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", (s or "").lower())).strip()


def canon_of(name, emails):
    """-> (canonical|None, review_reason|None)"""
    hits = {c for c, v in aliases.items() if set(emails) & set(v["emails"])}
    if len(hits) == 1:
        return hits.pop(), None
    if len(hits) > 1:
        return None, f"emails match several clients: {sorted(hits)}"
    n = norm(name)
    if not n:
        return None, "no name found"
    best, score = None, 0
    for c, v in aliases.items():
        for cand in set(v["names"]) | {norm(c)}:
            s = 1.0 if cand == n else SequenceMatcher(None, cand, n).ratio()
            if s > score:
                best, score = c, s
    if score >= MERGE:
        return best, None
    if score >= MAYBE:
        return None, f"'{name}' looks like '{best}' ({score:.2f}); merge in aliases.json if same person"
    return None, "new"


def register(name, emails):
    canon = name if name != name.lower() else name.title()
    aliases[canon] = {"names": [norm(name)], "emails": sorted(emails)}
    return canon


def learn(c, name, emails):
    v = aliases[c]
    if norm(name) and norm(name) not in v["names"]:
        v["names"].append(norm(name))
    v["emails"] = sorted(set(v["emails"]) | set(emails))


review = []
recs = sorted(M.data.items(), key=lambda kv: kv[1]["date"])  # first-seen name becomes canonical
for rid, r in recs:  # pass 1: fulfillment builds the client list
    if r.get("call_type") != "fulfillment":
        continue
    f = r.get("fulfillment") or {}
    name = f.get("client_name") or r.get("counterparty") or ""
    c, why = canon_of(name, r["ext_emails"])
    if why == "new":
        c = register(name, r["ext_emails"])
    elif c:
        learn(c, name, r["ext_emails"])
    else:
        review.append({"rid": rid, "title": r["title"], "date": r["date"], "reason": why})
    M.update(rid, client=c)
for rid, r in recs:  # pass 2: sales prospects that became clients (lookup only, never creates clients)
    if r.get("call_type") == "sales":
        s = r.get("sales") or {}
        c, _ = canon_of(s.get("prospect") or r.get("counterparty"), r["ext_emails"])
        M.update(rid, became_client=c)
M.save()
save_json(apath, aliases)
save_json(P.out / "needs_review.json", review)
print(f"{len(aliases)} clients, {len(review)} need review -> {P.out / 'needs_review.json'}")
