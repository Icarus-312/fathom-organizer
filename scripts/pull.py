#!/usr/bin/env python3
"""Step 1. Pull Fathom calls with full transcripts into cache/meetings.json (resumable, merged by id)."""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from common import cli, load_json, save_json

a, P = cli("Pull calls from Fathom", ("--days", dict(type=int, help="only the last N days; default all")))
key = P.get("FATHOM_API_KEY") or sys.exit("FATHOM_API_KEY missing (profile .env or environment)")
API = "https://api.fathom.ai/external/v1/meetings"
path = P.cache / "meetings.json"
have = {m["recording_id"]: m for m in load_json(path, [])}


def get(url):
    delay = 2
    for _ in range(8):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"X-Api-Key": key}), timeout=60))
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                sys.exit(f"Fathom said HTTP {e.code}. Check FATHOM_API_KEY.")
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(delay)
        delay = min(delay * 2, 60)
    sys.exit("Fathom kept failing")


q = {"limit": 50, "include_transcript": "true", "include_summary": "true"}
if a.days:
    q["created_after"] = (datetime.now(timezone.utc) - timedelta(days=a.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
cursor = None
while True:
    data = get(f"{API}?{urllib.parse.urlencode({**q, **({'cursor': cursor} if cursor else {})})}")
    for m in data["items"]:
        have[m["recording_id"]] = m
    print(f"pulled {len(have)} calls", flush=True)
    cursor = data.get("next_cursor")
    if not cursor:
        break
    time.sleep(1.5)
save_json(path, list(have.values()))
print(f"done: {len(have)} calls -> {path}")
