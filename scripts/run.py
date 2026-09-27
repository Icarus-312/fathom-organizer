#!/usr/bin/env python3
"""Run the whole pipeline: pull -> classify_type -> extract -> resolve -> organize -> report -> drive.
python3 scripts/run.py --profile NAME [--days 30] [--until type] [--local-only] [--limit N]
"""
import argparse, subprocess, sys
from pathlib import Path

S = Path(__file__).parent
p = argparse.ArgumentParser()
p.add_argument("--profile", required=True)
p.add_argument("--days", type=int)
p.add_argument("--limit", type=int)
p.add_argument("--until", choices=["type"], help="stop after the type gate so you can eyeball it")
p.add_argument("--local-only", action="store_true")
a = p.parse_args()
pr = ["--profile", a.profile]
steps = [("pull.py", pr + (["--days", str(a.days)] if a.days else [])),
         ("classify_type.py", pr + (["--limit", str(a.limit)] if a.limit else []))]
if not a.until:
    steps += [("extract.py", pr), ("resolve_clients.py", pr), ("organize.py", pr), ("report.py", pr)]
    if not a.local_only:
        steps.append(("drive_upload.py", pr))
for script, args in steps:
    print(f"\n=== {script} ===", flush=True)
    if subprocess.call([sys.executable, str(S / script)] + args):
        sys.exit(f"{script} failed")
