#!/usr/bin/env python3
"""Step 7. Mirror out/tree into the profile's Google Drive root folder (DRIVE_ROOT_FOLDER_ID).
Auth: OAuth desktop client at profiles/<name>/oauth-client.json (see SETUP.md). Token cached beside it.
Idempotent: manifest remembers each Drive file id; a changed path MOVES the file, never duplicates it.
--sweep-root moves loose files sitting in the Drive root (e.g. old Zapier drops) whose name matches a known
call title into _Superseded/ (recoverable, never deleted).
"""
import json, re, sys
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from common import *

a, P = cli("Upload tree to Drive", ("--dry-run", dict(action="store_true")),
           ("--sweep-root", dict(action="store_true")), ("--limit", dict(type=int)))
OFFERS = [o.strip() for o in P.get("OFFERS", "").split(",") if o.strip()]
def root_for(offer):  # one Drive root per offer: DRIVE_ROOT_<OFFER_SLUG>, else the single DRIVE_ROOT_FOLDER_ID
    key = "DRIVE_ROOT_" + re.sub(r"[^A-Z0-9]+", "_", offer.upper()).strip("_") if offer else "DRIVE_ROOT_FOLDER_ID"
    if not P.get(key):  # first run: create the root folder in My Drive and remember its id
        if a.dry_run:
            return f"DRY-root-{offer}"
        fid = call("POST", API, json={"name": offer or "Fathom Calls", "mimeType": "application/vnd.google-apps.folder"})["id"]
        with open(P.dir / ".env", "a") as f:
            f.write(f"{key}={fid}\n")
        P.env[key] = fid
        print(f"created Drive root '{offer}' -> {key}")
    return P.get(key)
SCOPES = ["https://www.googleapis.com/auth/drive"]
tok, client = P.dir / "oauth-token.json", P.dir / "oauth-client.json"
creds = Credentials.from_authorized_user_file(str(tok), SCOPES) if tok.exists() else None
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not client.exists():
            sys.exit(f"missing {client}. Follow the Google Drive section of SETUP.md")
        creds = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES).run_local_server(port=0)
    tok.write_text(creds.to_json())
    tok.chmod(0o600)
S = requests.Session()
API, UP = "https://www.googleapis.com/drive/v3/files", "https://www.googleapis.com/upload/drive/v3/files"


def call(method, url, **kw):
    if creds.expired:
        creds.refresh(Request())
    for i in range(6):
        r = S.request(method, url, headers={"Authorization": f"Bearer {creds.token}"}, **kw)
        if r.status_code in (429, 500, 502, 503) and i < 5:
            time.sleep(2 ** i)
            continue
        r.raise_for_status()
        return r.json() if r.content else {}


def q(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


folders = {}


def folder(parent, name):
    if (parent, name) in folders:
        return folders[(parent, name)]
    res = call("GET", API, params={"q": f"'{parent}' in parents and name='{q(name)}' and trashed=false and mimeType='application/vnd.google-apps.folder'", "fields": "files(id)"})["files"]
    fid = res[0]["id"] if res else (f"DRY-{name}" if a.dry_run else call("POST", API, json={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]})["id"])
    folders[(parent, name)] = fid
    return fid


def ensure_path(folder_path):
    parts = folder_path.split("/")
    cur = root
    if OFFERS:  # first path part is the offer name = its own Drive root
        cur, parts = root_for(parts[0]), parts[1:]
    for part in parts:
        cur = folder(cur, part)
    return cur


def existing(parent, name):
    res = call("GET", API, params={"q": f"'{parent}' in parents and name='{q(name)}' and trashed=false", "fields": "files(id)"})["files"]
    return res[0]["id"] if res else None


def create(parent, name, text, desc):
    b = "fathomorg"
    body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps({'name': name, 'parents': [parent], 'description': desc or ''})}\r\n"
            f"--{b}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n{text}\r\n--{b}--").encode()
    if creds.expired:
        creds.refresh(Request())
    r = S.post(UP, params={"uploadType": "multipart", "fields": "id"}, data=body,
               headers={"Authorization": f"Bearer {creds.token}", "Content-Type": f"multipart/related; boundary={b}"})
    r.raise_for_status()
    return r.json()["id"]


root = root_for("" if not OFFERS else OFFERS[0])
M = Manifest(P)
tree = P.out / "tree"
todo = [(rid, r) for rid, r in M.data.items() if r.get("path")]
if a.limit:
    todo = todo[: a.limit]
made = moved = skipped = 0
for i, (rid, r) in enumerate(todo, 1):
    d = r.get("drive") or {}
    if d.get("path") == r["path"]:
        skipped += 1
        continue
    folder_path, name = r["path"].rsplit("/", 1)
    parent = ensure_path(folder_path)
    if d.get("id"):  # path changed since last upload: move + rename
        if not a.dry_run:
            old = call("GET", f"{API}/{d['id']}", params={"fields": "parents"})["parents"]
            call("PATCH", f"{API}/{d['id']}", params={"addParents": parent, "removeParents": ",".join(old)}, json={"name": name})
        fid, moved = d["id"], moved + 1
    else:
        fid = None if a.dry_run else existing(parent, name)  # adopt a same-named file instead of duplicating
        if not fid:
            fid = f"DRY-{name}" if a.dry_run else create(parent, name, (tree / r["path"]).read_text(), r.get("url"))
            made += 1
        else:
            skipped += 1
    if not a.dry_run:
        M.update(rid, drive={"id": fid, "path": r["path"]})
    if i % 25 == 0:
        print(f"  {i}/{len(todo)} (created {made}, moved {moved})", flush=True)
M.save()
print(f"drive: created {made}, moved {moved}, unchanged {skipped}{' (dry run)' if a.dry_run else ''}")

if a.sweep_root:
    titles = {norm for norm in (re.sub(r"[^a-z0-9]", "", str(r["title"]).lower()) for r in M.data.values()) if norm}
    loose = call("GET", API, params={"q": f"'{root}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'", "fields": "files(id,name)", "pageSize": 1000})["files"]
    hit = [f for f in loose if any(t in re.sub(r"[^a-z0-9]", "", f["name"].lower()) for t in titles)]
    print(f"root has {len(loose)} loose files, {len(hit)} match known calls")
    if not a.dry_run and hit:
        dest = folder(root, "_Superseded")
        for f in hit:
            call("PATCH", f"{API}/{f['id']}", params={"addParents": dest, "removeParents": root})
        print(f"moved {len(hit)} to _Superseded/")
