# fathom-organizer

Point it at a Fathom API key. It reads every call transcript in full, decides sales vs fulfillment, tells you why deals were lost, files client calls by client, and mirrors it all into Google Drive.

```
Sales/2026/09/2026-09-14/Won|Lost|Follow-up/Dana Ruiz - Discovery Call.md
Clients/Brie Mobley/2026/09/2026-09-22/Client Call.md
_Internal/...   _Unmatched/...   report.md
```

Quick start (5 commands, ~10 min to first result on 30 days of calls):

```bash
pip install -r requirements.txt
cp -r profiles.example profiles/mybiz && mv profiles/mybiz/.env.example profiles/mybiz/.env
# edit profiles/mybiz/.env (Fathom key, timezone) and copy context.md.example to context.md, fill it in
python3 scripts/run.py --profile mybiz --days 30 --until type      # check the sales/fulfillment split
python3 scripts/run.py --profile mybiz --days 30 --local-only        # full run, local files + report
```

Works as a Claude Code skill (drop this folder in `~/.claude/skills/fathom-organizer`) or plain Python 3.9+. Read [SETUP.md](SETUP.md) for the full guide and how it works.
