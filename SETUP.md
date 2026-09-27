# Setup guide and architecture

## What you get
Every Fathom call read in full, then filed:

```
<Drive root or out/tree>/
  Sales/<YYYY>/<MM>/<YYYY-MM-DD>/<Won|Lost|Follow-up>/<Prospect> - <title>.md
  Clients/<Client>/<YYYY>/<MM>/<YYYY-MM-DD>/<title>.md
  _Internal/<YYYY>/<MM>/<date>/     team calls, group trainings, office hours
  _Unmatched/<YYYY>/<MM>/<date>/    interviews, low confidence, unresolved client
report.md                          scoreboard, unbeaten objections in lost deals, calls per client
```
Each file has a header (type, date, Fathom link, outcome + evidence quote + objections for sales), Fathom's own summary, and the full transcript.

## Prerequisites (10 minutes)
1. **Python 3.9+** and `pip install -r requirements.txt`.
2. **A Fathom API key.** Fathom, Settings, API Access, generate a key. One key = one Fathom account = one profile.
3. **An LLM.** Either:
   - the `claude` CLI logged in (Claude Code), no extra config, or
   - `ANTHROPIC_API_KEY` in the profile `.env` (or your shell).
4. **Google Drive (optional).** Only needed for Drive upload. Use `--local-only` to skip. See "Google Drive setup".

## Install
- As a Claude Code skill: clone into `~/.claude/skills/fathom-organizer` and tell Claude "set up the Fathom organizer". It walks you through the profile.
- Or plain Python: clone anywhere and run the scripts yourself.

## Create a profile (5 minutes)
A profile is one Fathom account's config, cache and output. Make one per client/business.
```bash
cp -r profiles.example profiles/mybiz
mv profiles/mybiz/.env.example profiles/mybiz/.env
mv profiles/mybiz/context.md.example profiles/mybiz/context.md
```
1. Edit `.env`: `FATHOM_API_KEY`, `TIMEZONE` (calls are dated in this zone).
2. Edit `context.md`. This is the most important 3 minutes of setup: who the host is, what they sell, who is on the team (so team members are never mistaken for clients), any call-title patterns, recurring group calls. The classifier reads this before every call.

## First run: 30 days, gate first
```bash
python3 scripts/run.py --profile mybiz --days 30 --until type
```
Pulls calls with full transcripts, reads each one, and prints the sales / fulfillment / internal / group / other tally with 10 samples per type. **Eyeball it.** If types are wrong, improve `context.md` and re-run classify with `python3 scripts/classify_type.py --profile mybiz --redo`. Nothing else has been spent yet.

Happy with it? Run the rest:
```bash
python3 scripts/run.py --profile mybiz --days 30 --local-only
```
Open `profiles/mybiz/out/report.md` and browse `profiles/mybiz/out/tree/`. Then drop `--days` for full history. Re-runs only handle new calls.

Rough cost/time: type gate ~5 s/call (small model), 6 in parallel. Sales/fulfillment analysis ~20 s/call, 4 in parallel. 200 calls is roughly 15 minutes.

## Fix client names
Open `profiles/mybiz/needs_review.json` (calls it could not confidently attach to a client) and `aliases.json`. To merge "Bob Smith" and "Robert Smith": move the second entry's `names` and `emails` under the first, delete the second, then:
```bash
python3 scripts/resolve_clients.py --profile mybiz && python3 scripts/organize.py --profile mybiz
```
(and `drive_upload.py` if using Drive: files that changed folder are moved, not duplicated.)

## Google Drive setup (15 minutes, once per Google account)
Why OAuth and not a service account: a service account has no storage of its own, so Google refuses to let it write into your Drive. OAuth acts as you.
1. Create a Drive folder for the output. Its ID is the last part of the URL. Put it in `.env` as `DRIVE_ROOT_FOLDER_ID`.
2. In [Google Cloud Console](https://console.cloud.google.com/): create a project, then APIs & Services, enable **Google Drive API**.
3. OAuth consent screen: External, add yourself under Test users.
4. Credentials, Create credentials, **OAuth client ID**, application type **Desktop app**. Download the JSON to `profiles/mybiz/oauth-client.json`.
5. `python3 scripts/drive_upload.py --profile mybiz --dry-run` (first run opens a browser to approve; token saves to `oauth-token.json`).
6. Real run: `python3 scripts/run.py --profile mybiz` (no `--local-only`).
Loose files already sitting in the Drive root from an old automation (e.g. Zapier) can be moved to `_Superseded/` with `python3 scripts/drive_upload.py --profile mybiz --sweep-root`. Nothing is ever deleted.

## How it works (architecture)
```
Fathom API
   |  pull.py            full transcripts, cursor-paginated, retries 429s
   v
cache/meetings.json      raw truth. Never edited. Re-classify without re-hitting Fathom.
   |  classify_type.py   THE GATE. Small model reads the whole call -> sales|fulfillment|internal|group|other
   v                     + confidence + counterparty. Low confidence goes to _Unmatched, never a forced guess.
out/manifest.json        one record per call (recording_id), grows at each step
   |
   +-- sales ---------> extract.py (prompts/sales.md)        outcome + evidence quote + objections + next step
   +-- fulfillment ---> extract.py (prompts/fulfillment.md)  client name, company, topic
   |
   |  resolve_clients.py names + invitee emails -> ONE canonical client (aliases.json, yours to edit)
   |  organize.py        builds out/tree/ from scratch every run (staging)
   |  report.py          out/report.md
   |  drive_upload.py    mirrors tree to Drive; manifest remembers file ids so re-runs move, not duplicate
   v
Drive folder / local tree / report
```
Design choices worth knowing:
- **Classify first, then branch.** Most calls are one type, so the expensive analysis prompt only runs on the calls that need it. The type result is a checkpoint you can inspect before spending more.
- **Cache first.** Raw Fathom data is stored once. Prompts can change and you re-run without re-pulling.
- **Manifest keyed by `recording_id`.** Dedupe never depends on file names. Every step skips finished work, so any step can crash and be re-run.
- **Email beats name.** Client matching uses external invitee emails first, fuzzy name second (>=0.88 merges, 0.75 to 0.88 goes to review). Never a silent guess.
- **Profiles keep accounts apart.** Different keys, contexts, aliases and Drive roots never mix. Nothing client-specific lives in code; it lives in `context.md` and the prompts in `prompts/`.
- **A verbal yes counts as won.** Outcome is judged from the call only. It does not check your payment processor or CRM.
- **Privacy.** Transcripts live on your machine and in your Drive. The only place text leaves is the LLM call.

## Troubleshooting
- `Fathom said HTTP 401`: wrong key in `.env`.
- Lots of 429s: normal, the puller backs off and continues.
- Calls with no transcript are filed nowhere (skipped); they show in the manifest as `no_transcript`.
- Everything lands in `_Unmatched`: `context.md` is too thin, or confidence is low. Run with `--min-confidence 0.5` on `organize.py`, or improve the context.
- A team member became a "client": add them to the Team list in `context.md`, then `classify_type.py --redo`.
