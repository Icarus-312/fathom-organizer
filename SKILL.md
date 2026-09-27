---
name: fathom-organizer
description: Organize every Fathom call recording by reading the full transcripts. Classifies each call as sales or fulfillment first, extracts sales outcomes (won/lost/follow-up) and the objections that lost deals, files fulfillment calls by client, and mirrors the tree into Google Drive. Use when the user says "organize my Fathom calls", "sort my calls by client", "why are we losing deals", "set up the Fathom organizer", or hands over a Fathom API key. Supports many accounts via profiles.
---

# Fathom Organizer

Reads full Fathom transcripts and files them: `Sales/<Y>/<M>/<date>/<Won|Lost|Follow-up>/`, `Clients/<Name>/<Y>/<M>/<date>/`, `_Internal/`, `_Unmatched/`, plus `out/report.md` (sales scoreboard, unbeaten objections in lost deals, calls per client). Full setup + architecture: `SETUP.md`.

## Workflow (do these in order; skill dir = this folder)

1. **Profile.** One profile per Fathom account, at `profiles/<name>/`. If it does not exist, copy `profiles.example/` to it, rename `.env.example` to `.env`, and ask the user for: Fathom API key, timezone, and (for `context.md`) who the host is, what they sell, who is on the team, any call-title conventions, recurring group calls. Write `context.md` from their answers. Never print the key back.
   - **One Fathom account, multiple offers** (e.g. two separate businesses sharing a key): set `OFFERS=Offer A,Offer B` in `.env` and describe how to tell them apart in `context.md`. The type gate then decides the offer first; each offer gets its own top-level folder locally and its own Drive root (`DRIVE_ROOT_<OFFER_SLUG>`, auto-created on first upload).
2. **Type gate first.** `python3 scripts/run.py --profile NAME --days 30 --until type`. Shows the sales / fulfillment / internal / group / other tally with 10 samples each. Show it to the user; fix `context.md` and run `scripts/classify_type.py --profile NAME --redo` if the types look wrong.
3. **Everything else.** `python3 scripts/run.py --profile NAME --local-only` (drop `--local-only` once `DRIVE_ROOT_FOLDER_ID` and `oauth-client.json` are set up). Omit `--days` for full history. Re-runs only process new calls.
4. **Review.** Open `profiles/NAME/out/report.md` and `needs_review.json`. To merge two names into one client, edit `profiles/NAME/aliases.json` (move names/emails under one client), then run `scripts/resolve_clients.py`, `organize.py`, `drive_upload.py`.

## Rules
- Steps are separate scripts, all take `--profile`. Every step is resumable and skips finished work.
- LLM calls use `ANTHROPIC_API_KEY` if set, else the logged-in `claude` CLI. Transcripts stay on this machine except for those LLM calls.
- Never commit `profiles/*` (gitignored). Never put a key in a chat reply or a file outside `profiles/<name>/.env`.
- Sales outcome comes from the call alone (a verbal yes counts as won). Say so when reporting.
- Verify before reporting numbers: `wc -l`/count files in `out/tree` against the manifest; don't trust a "done" from the script alone.
