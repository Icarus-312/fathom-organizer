#!/usr/bin/env python3
"""Step 3. Branch on type: sales -> outcome/objections; fulfillment -> client name/topic."""
from common import *

a, P = cli("Extract per-branch details", ("--workers", dict(type=int, default=4)))
model = P.get("MODEL_EXTRACT", "claude-sonnet-5")
by_id = {str(m["recording_id"]): m for m in load_json(P.cache / "meetings.json", [])}
M = Manifest(P)
prompts = {"sales": ("sales.md", "sales"), "fulfillment": ("fulfillment.md", "fulfillment")}
todo = [(rid, r) for rid, r in M.data.items()
        if r.get("call_type") in prompts and prompts[r["call_type"]][1] not in r and rid in by_id]
print(f"extracting {len(todo)} calls with {model}")
systems = {t: system_prompt(f, P) for t, (f, _) in prompts.items()}


def one(item):
    rid, r = item
    t = r["call_type"]
    out = llm_json(systems[t], render(by_id[rid]), model)
    M.update(rid, **{prompts[t][1]: out})
    print(f"  {t:<11} {r['title']}", flush=True)


pmap(one, todo, a.workers)
M.save()
