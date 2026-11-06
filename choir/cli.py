"""agent-choir: turn what your coding agents did into an a cappella song.

  choir collect --claude --since 24h -o work.json   # or --git REPO..., --json FILE
  choir write work.json -o song.json                # Claude writes the lyrics
  choir sing song.json                              # estimate only (no spend)
  choir sing song.json --yes                        # render on every provider
  choir video song.json takes/<slug>/minimax-2.6.mp3 -o tweet.mp4
  choir run --claude --since 24h --providers minimax-2.6 --yes   # all of it
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from choir import lyrics, providers, sing, video, work
from choir.song import Song


def _collect(args) -> list[work.Agent]:
    since = work.parse_since(args.since)
    agents: list[work.Agent] = []
    if args.claude:
        agents += work.from_claude(Path(args.claude_dir).expanduser(), since)
    for repo in args.git or []:
        a = work.from_git(Path(repo).expanduser(), since)
        if a:
            agents.append(a)
    if args.json:
        agents += work.from_json(Path(args.json))
    agents = work.top_agents(agents)
    if not agents:
        sys.exit("no agent work found; widen --since or pass --json examples/work.json")
    return agents


def _add_collect_args(p):
    p.add_argument("--claude", action="store_true", help="read Claude Code session transcripts")
    p.add_argument("--claude-dir", default="~/.claude/projects")
    p.add_argument("--git", nargs="*", metavar="REPO", help="git repos; one agent per repo")
    p.add_argument("--json", metavar="FILE", help="hand-written work file (see examples/work.json)")
    p.add_argument("--since", default="24h", help="window, e.g. 90m, 24h, 3d")


def _write(agents, no_llm: bool) -> Song:
    song = lyrics.template(agents) if no_llm else lyrics.write(agents)
    problems = song.problems()
    if problems:
        sys.exit("song failed checks: " + "; ".join(problems))
    return song


def _print_song(song: Song) -> None:
    print(f"\n♪ {song.title}\n")
    for s in song.sections:
        print(f"[{s.label}] {', '.join(s.singers) or 'All'}")
        for line in s.lines:
            print(f"  {line}")
    print()


def _sing(song: Song, keys: list[str], out: Path, yes: bool) -> list[dict] | None:
    provs = providers.get(keys)
    rows, total = sing.estimate(song, provs)
    print("Estimated cost (fal.ai list prices):")
    for k, c in rows:
        print(f"  {k:<12} ~${c:.2f}")
    print(f"  {'total':<12} ~${total:.2f}")
    if not yes:
        print("\nNothing spent. Re-run with --yes to render.")
        return None
    dest = out / song.slug()
    results = sing.bakeoff(song, provs, dest)
    print(f"\nTakes in {dest}/ — open index.html to compare.")
    return results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="choir", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("collect", help="gather what the agents did")
    _add_collect_args(p)
    p.add_argument("-o", "--out", default="work.json")

    p = sub.add_parser("write", help="write the song from a work file")
    p.add_argument("work")
    p.add_argument("-o", "--out", default="song.json")
    p.add_argument("--no-llm", action="store_true", help="offline template lyrics")

    p = sub.add_parser("sing", help="render the song on music models")
    p.add_argument("song")
    p.add_argument("--providers", default=",".join(providers.DEFAULT),
                   help=f"comma list from: {', '.join(providers.PROVIDERS)}")
    p.add_argument("--out", default="takes")
    p.add_argument("--yes", action="store_true", help="actually spend; without it, estimate only")

    p = sub.add_parser("video", help="make a tweetable MP4 from one take")
    p.add_argument("song")
    p.add_argument("audio")
    p.add_argument("-o", "--out", default=None)

    p = sub.add_parser("run", help="collect -> write -> sing -> video")
    _add_collect_args(p)
    p.add_argument("--providers", default="minimax-2.6")
    p.add_argument("--out", default="takes")
    p.add_argument("--no-llm", action="store_true")
    p.add_argument("--yes", action="store_true")

    p = sub.add_parser("providers", help="list singing models")

    args = ap.parse_args(argv)

    if args.cmd == "providers":
        for prov in providers.PROVIDERS.values():
            print(f"{prov.key:<12} {prov.model:<28} {prov.blurb}")
        return

    if args.cmd == "collect":
        agents = _collect(args)
        work.save(agents, Path(args.out))
        for a in agents:
            print(f"{a.project} ({a.id}): {len(a.facts)} facts")
        print(f"-> {args.out}  (read it before writing: this text goes into a public song)")
        return

    if args.cmd == "write":
        song = _write(work.top_agents(work.from_json(Path(args.work))), args.no_llm)
        song.save(Path(args.out))
        _print_song(song)
        print(f"-> {args.out}")
        return

    if args.cmd == "sing":
        _sing(Song.load(Path(args.song)), [k.strip() for k in args.providers.split(",") if k.strip()], Path(args.out), args.yes)
        return

    if args.cmd == "video":
        song = Song.load(Path(args.song))
        audio = Path(args.audio)
        timings = None
        takes = audio.parent / "takes.json"
        if takes.exists():
            for t in json.loads(takes.read_text()):
                if t.get("file") == audio.name:
                    timings = t.get("timings")
        out = Path(args.out) if args.out else audio.with_suffix(".mp4")
        video.render(song, audio, out, timings)
        print(f"-> {out}")
        return

    if args.cmd == "run":
        agents = _collect(args)
        song = _write(agents, args.no_llm)
        _print_song(song)
        keys = [k.strip() for k in args.providers.split(",") if k.strip()]
        results = _sing(song, keys, Path(args.out), args.yes)
        for r in results or []:
            if r.get("file"):
                dest = Path(args.out) / song.slug()
                out = video.render(song, dest / r["file"], dest / f"{r['provider']}.mp4", r.get("timings"))
                print(f"-> {out}")
        return


if __name__ == "__main__":
    main()
