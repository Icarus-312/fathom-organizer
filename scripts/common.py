"""Shared helpers: profiles, manifest, LLM call, parallel map. Stdlib only."""
import argparse, json, os, re, subprocess, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"


def parse_env(path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                env[m[1]] = m[2].strip("\"'")
    return env


class Profile:
    """One client / one Fathom account. Everything it owns lives in profiles/<name>/."""

    def __init__(self, name):
        self.name = name
        self.dir = ROOT / "profiles" / name
        if not self.dir.is_dir():
            sys.exit(f"no profile '{name}'. Create profiles/{name}/ from profiles.example/ (see SETUP.md)")
        self.env = parse_env(self.dir / ".env")
        self.cache, self.out = self.dir / "cache", self.dir / "out"
        self.cache.mkdir(exist_ok=True)
        self.out.mkdir(exist_ok=True)
        self.tz = ZoneInfo(self.get("TIMEZONE", "UTC"))
        self.context = (self.dir / "context.md").read_text() if (self.dir / "context.md").exists() else ""

    def get(self, k, default=None):
        return self.env.get(k) or os.environ.get(k) or default


def cli(desc, *extra):
    """Standard CLI: --profile plus (flag, kwargs) pairs."""
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--profile", required=True)
    for flag, kw in extra:
        p.add_argument(flag, **kw)
    a = p.parse_args()
    return a, Profile(a.profile)


def load_json(path, default):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def save_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    os.replace(tmp, path)


class Manifest:
    """out/manifest.json: recording_id -> everything we know. Thread-safe, autosaves."""

    def __init__(self, profile):
        self.path = profile.out / "manifest.json"
        self.data = load_json(self.path, {})
        self.lock = threading.Lock()
        self.n = 0

    def update(self, rid, **kv):
        with self.lock:
            self.data.setdefault(str(rid), {}).update(kv)
            self.n += 1
            if self.n % 10 == 0:
                save_json(self.path, self.data)

    def save(self):
        with self.lock:
            save_json(self.path, self.data)


def call_date(m, tz):
    iso = m.get("scheduled_start_time") or m.get("recording_start_time") or m["created_at"]
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(tz).strftime("%Y-%m-%d")


def render(m):
    """Meeting -> prompt text. Full transcript, nothing trimmed."""
    lines = [f"{s['speaker']['display_name']}: {s['text']}" for s in (m.get("transcript") or [])]
    inv = "; ".join(f"{i.get('name')} <{i.get('email')}> {'EXTERNAL' if i.get('is_external') else 'team'}"
                    for i in (m.get("calendar_invitees") or []))
    return f"TITLE: {m.get('title')}\nINVITEES: {inv}\nDATE: {m['created_at']}\n\nTRANSCRIPT:\n" + "\n".join(lines)


def llm_json(system, user, model, tries=3):
    """One prompt in, one JSON object out. ANTHROPIC_API_KEY if set, else the `claude` CLI."""
    last = None
    for _ in range(tries):
        try:
            key = os.environ.get("ANTHROPIC_API_KEY")
            if key:
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    json.dumps({"model": model, "max_tokens": 2000, "system": system,
                                "messages": [{"role": "user", "content": user}]}).encode(),
                    {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
                out = json.load(urllib.request.urlopen(req, timeout=180))["content"][0]["text"]
            else:
                out = subprocess.run(["claude", "-p", "--model", model, "--system-prompt", system],
                                     input=user, capture_output=True, text=True, timeout=300).stdout
            return json.loads(out[out.index("{"): out.rindex("}") + 1])
        except Exception as e:  # bad JSON, timeout, 429: retry
            last = e
            time.sleep(3)
    raise RuntimeError(f"LLM failed: {last}")


def system_prompt(name, profile):
    txt = (PROMPTS / name).read_text()
    if profile.context.strip():
        txt += "\n\nHOST CONTEXT (from the user; trust it):\n" + profile.context
    return txt


def pmap(fn, items, workers):
    """Run fn over items in parallel; print progress; exceptions are reported, not fatal."""
    done = [0]

    def wrap(it):
        try:
            return fn(it)
        except Exception as e:
            print(f"  FAILED {e}", flush=True)
        finally:
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(items):
                print(f"  {done[0]}/{len(items)}", flush=True)

    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(wrap, items))
