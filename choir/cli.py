"""agent-choir: your coding agents sing what they just did.

  choir install claude        add the Stop hook to ~/.claude/settings.json
  choir install codex         add the notify hook to ~/.codex/config.toml
  choir say "text" [--agent X --project Y]   sing a line yourself
  choir demo                  four fake terminals sing (costs a few clips)
  choir reel -o reel.mp4      campaign video from what your agents sang
  choir providers | voices | doctor | mute | unmute | budget
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from choir import agents, config, core, ledger, providers, reel
from choir.agents import Turn
from choir.cast import CAST


# --- hooks (must never block or fail the agent) ---------------------------

def _detach(kind: str, payload: dict) -> None:
    """Hand the turn to a background process and return at once."""
    spool = config.STATE_DIR / "spool"
    spool.mkdir(parents=True, exist_ok=True)
    f = spool / f"{time.time_ns()}.json"
    f.write_text(json.dumps({"kind": kind, "payload": payload, "env": {k: v for k, v in os.environ.items() if k in agents._TERMINAL_VARS}}))
    subprocess.Popen([sys.executable, "-m", "choir", "_perform", str(f)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def hook(kind: str, argv_payload: str | None) -> None:
    try:
        if os.environ.get("CHOIR_MUTE"):
            return
        if kind == "claude":
            payload = json.loads(sys.stdin.read() or "{}")
            if payload.get("stop_hook_active"):
                return
        else:  # codex passes JSON as the last argument
            payload = json.loads(argv_payload or "{}")
        _detach(kind, payload)
    except Exception as e:  # never break the agent
        core._log(f"hook {kind} error: {e}")


def _perform(spool_file: str) -> None:
    f = Path(spool_file)
    try:
        job = json.loads(f.read_text())
        env = job.get("env") or {}
        if job["kind"] == "claude":
            turn = agents.from_claude_hook(job["payload"], env)
        else:
            turn = agents.from_codex_notify(job["payload"], env)
        if turn:
            core.perform(turn, echo=lambda *_: None)
    except Exception as e:
        core._log(f"perform error: {e}")
    finally:
        f.unlink(missing_ok=True)


# --- install -------------------------------------------------------------

def _hook_cmd(kind: str) -> str:
    return f"{sys.executable} -m choir hook {kind}"


def install_claude(settings_path: Path) -> str:
    data = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    stops = data.setdefault("hooks", {}).setdefault("Stop", [])
    cmd = _hook_cmd("claude")
    if any("choir hook claude" in h.get("command", "") for blk in stops for h in blk.get("hooks", [])):
        return "already installed"
    if settings_path.exists():
        shutil.copy(settings_path, settings_path.with_suffix(".json.bak"))
    stops.append({"hooks": [{"type": "command", "command": cmd, "async": True}]})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n")
    return f"added Stop hook to {settings_path} (backup: {settings_path.name}.bak)"


def install_codex(cfg_path: Path) -> str:
    line = "notify = " + json.dumps([sys.executable, "-m", "choir", "hook", "codex"])
    text = cfg_path.read_text() if cfg_path.exists() else ""
    if "choir" in text and "notify" in text:
        return "already installed"
    if any(l.strip().startswith("notify") for l in text.splitlines()):
        return f"{cfg_path} already has a notify command; Codex allows one. Replace it with:\n  {line}"
    # notify must be a top-level key, so it goes before the first [table].
    lines = text.splitlines()
    at = next((i for i, l in enumerate(lines) if l.strip().startswith("[")), len(lines))
    lines.insert(at, line)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if cfg_path.exists():
        shutil.copy(cfg_path, cfg_path.with_suffix(".toml.bak"))
    cfg_path.write_text("\n".join(lines) + "\n")
    return f"added notify to {cfg_path}"


# --- demo ----------------------------------------------------------------

DEMO = [
    ("demo:api", "billing-api", "Fixed the midnight rate limiter bug, all two hundred tests pass"),
    ("demo:web", "website", "The pricing page loads in one second now, down from three"),
    ("demo:docs", "docs", "I wrote the hotkey guide and fixed eleven broken links"),
    ("demo:app", "desktop-app", "I need your okay before I ship the release tonight"),
]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="choir", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("hook", help="called by Claude Code / Codex")
    p.add_argument("kind", choices=["claude", "codex"])
    p.add_argument("payload", nargs="?")
    p = sub.add_parser("_perform")
    p.add_argument("spool")

    p = sub.add_parser("install", help="wire up an agent")
    p.add_argument("agent", choices=["claude", "codex"])

    p = sub.add_parser("say", help="sing a line now")
    p.add_argument("text")
    p.add_argument("--agent", default=None, help="terminal/agent key (default: this terminal)")
    p.add_argument("--project", default=Path.cwd().name)
    p.add_argument("--raw", action="store_true", help="sing the text as is, no summarizing")
    p.add_argument("--no-play", action="store_true")
    p.add_argument("--provider")

    p = sub.add_parser("demo", help="four fake terminals sing, then a reel")
    p.add_argument("--provider")
    p.add_argument("--no-play", action="store_true")
    p.add_argument("-o", "--out", default="choir-demo.mp4")

    p = sub.add_parser("reel", help="campaign video from recent clips")
    p.add_argument("--since", type=float, default=60, help="minutes back (default 60)")
    p.add_argument("--last", type=int, default=8, help="at most this many clips")
    p.add_argument("--stagger", type=float, default=None, help="seconds between entrances; small = overlap like a round")
    p.add_argument("-o", "--out", default="choir-reel.mp4")

    sub.add_parser("providers", help="list singing back-ends")
    sub.add_parser("voices", help="the singers and who has them")
    sub.add_parser("doctor", help="check keys, player, ffmpeg")
    sub.add_parser("budget", help="today's spend")
    sub.add_parser("mute")
    sub.add_parser("unmute")
    sub.add_parser("reset-voices", help="free every singer")
    sub.add_parser("init", help="write an example config.toml")

    args = ap.parse_args(argv)
    s = config.load()

    if args.cmd == "hook":
        return hook(args.kind, args.payload)
    if args.cmd == "_perform":
        return _perform(args.spool)

    if args.cmd == "install":
        if args.agent == "claude":
            print(install_claude(Path.home() / ".claude" / "settings.json"))
        else:
            print(install_codex(Path.home() / ".codex" / "config.toml"))
        if not any(p.available() for p in providers.PROVIDERS.values()):
            print(f"next: put FAL_KEY=... or ELEVENLABS_API_KEY=... in {config.CONFIG_DIR / 'env'}")
        return

    if args.cmd in ("say", "demo") and getattr(args, "provider", None):
        s.provider = args.provider

    if args.cmd == "say":
        turn = Turn(agent=args.agent or agents.terminal_key() or f"cli:{os.getppid()}",
                    project=args.project, message=args.text, source="cli")
        s.min_words = 0
        entry = core.perform(turn, s, play=not args.no_play, line=args.text if args.raw else None)
        if entry is None:
            sys.exit(f"nothing sung; see {config.STATE_DIR / 'choir.log'}")
        return

    if args.cmd == "demo":
        s.min_words = 0
        done = []
        for agent, project, line in DEMO:
            e = core.perform(Turn(agent, project, line, "demo"), s, play=not args.no_play, line=line)
            if e:
                done.append(e)
        if done:
            out = reel.render(done, Path(args.out))
            print(f"-> {out}")
        return

    if args.cmd == "reel":
        es = ledger.entries(time.time() - args.since * 60)[-args.last:]
        es = [e for e in es if (ledger.clips_dir() / e["clip"]).exists()]
        print(f"-> {reel.render(es, Path(args.out), stagger=args.stagger)}")
        return

    if args.cmd == "providers":
        for p in providers.PROVIDERS.values():
            mark = "✓" if p.available() else " "
            cur = " (current)" if p.key == s.provider else ""
            print(f"{mark} {p.key:<16} {p.blurb}{cur}")
        print(f"\n✓ = key found. Keys go in your env or {config.CONFIG_DIR / 'env'}")
        return

    if args.cmd == "voices":
        seated = {v["singer"]: v["project"] for v in agents.seats().values()}
        for c in CAST:
            who = seated.get(c.name, "")
            print(f"{c.name:<7} {c.part:<13} pan {c.pan:+.2f}  {who}")
        return

    if args.cmd == "doctor":
        prov = providers.PROVIDERS.get(s.provider)
        from choir import audio
        print(f"provider   {s.provider}: {'key ok' if prov and prov.available() else 'MISSING ' + (prov.needs if prov else 'unknown provider')}")
        print(f"summarizer {s.summarizer} ({'ANTHROPIC_API_KEY set' if os.environ.get('ANTHROPIC_API_KEY') else 'no Anthropic key: plain first-sentence lines'})")
        print(f"player     {' '.join(audio.player() or ['NONE (install ffmpeg or pulseaudio-utils)'])}")
        print(f"ffmpeg     {audio.ffmpeg()}")
        print(f"budget     ${ledger.spent_today():.2f} of ${s.daily_budget_usd:.2f} today")
        print(f"muted      {s.muted}")
        print(f"log        {config.STATE_DIR / 'choir.log'}")
        return

    if args.cmd == "budget":
        print(f"${ledger.spent_today():.2f} of ${s.daily_budget_usd:.2f} spent today")
        return
    if args.cmd == "mute":
        config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (config.CONFIG_DIR / "mute").touch()
        print("muted")
        return
    if args.cmd == "unmute":
        (config.CONFIG_DIR / "mute").unlink(missing_ok=True)
        print("unmuted")
        return
    if args.cmd == "reset-voices":
        agents.reset_seats()
        print("every singer is free")
        return
    if args.cmd == "init":
        path = config.CONFIG_DIR / "config.toml"
        if path.exists():
            sys.exit(f"{path} exists")
        config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(config.EXAMPLE)
        print(f"-> {path}")
        return


if __name__ == "__main__":
    main()
