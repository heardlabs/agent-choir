"""Write the song from the agents' real work.

Claude writes it (Anthropic SDK when a key or ``ant`` profile is set, else the
local ``claude -p`` CLI). ``template`` is an offline, no-LLM fallback so the
pipeline can be exercised without any credentials.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from choir.cast import CAST, assign
from choir.song import BANNED, Section, Song
from choir.work import Agent

MODEL = "claude-opus-5-5"

SYSTEM = f"""You write lyrics for an a cappella group of AI coding agents who sing about the work they just did, like a crew singing on the way to a job.

The ensemble (each name is a singer; every agent was assigned one):
{chr(10).join(f"- {s.name}: {s.part}" for s in CAST)}
Grep only beatboxes and never sings words; never give Grep a section.

Write ONE original song, 45 to 75 seconds when sung:
- intro (All, 2 lines), then for each assigned singer a short verse (2 to 4 lines) where that singer brags or grumbles about its real work, a chorus (All, 4 lines) that repeats twice in the song, optionally a bridge, and an outro (All, 1 to 2 lines).
- Use the concrete facts given: real file names, commands, test counts, bugs. Specific beats generic. Developers should laugh in recognition.
- Short singable lines (4 to 10 words), strong rhyme, steady rhythm. Plain words the singers can pronounce; spell out symbols ("dot py", not ".py").
- Each verse's `singers` is exactly that one singer's name. Intro, chorus and outro use ["All"].
- The chorus is a catchy original hook about agents working while you're away. Do not quote, parody or echo any existing song. Never use: {", ".join(BANNED)}.
- Never include secrets, emails, URLs, customer or person names, or anything marked [redacted].
- `credits` maps each assigned singer's name to "project: one short phrase of what it did".
"""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "sections", "credits"],
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "singers", "lines"],
                "properties": {
                    "kind": {"type": "string", "enum": ["intro", "verse", "pre-chorus", "chorus", "bridge", "outro"]},
                    "singers": {"type": "array", "items": {"type": "string"}},
                    "lines": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "credits": {"type": "object", "additionalProperties": {"type": "string"}},
    },
}


def brief(agents: list[Agent]) -> str:
    roles = assign([a.id for a in agents])
    crew = [
        {"singer": roles[a.id].name, "part": roles[a.id].part, "project": a.project, "did": a.facts}
        for a in agents
    ]
    return "Today's crew and what each one did:\n" + json.dumps(crew, indent=2, ensure_ascii=False)


def _has_api_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    if shutil.which("ant"):
        r = subprocess.run(["ant", "auth", "status"], capture_output=True, text=True)
        return r.returncode == 0
    return False


def _via_sdk(user: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"lyricist declined: {getattr(resp, 'stop_details', None)}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("lyricist ran out of tokens")
    text = "".join(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def _via_cli(user: str) -> dict:
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("no Anthropic credentials and no `claude` CLI; use --no-llm or set ANTHROPIC_API_KEY")
    prompt = (
        SYSTEM
        + "\nReply with ONLY a JSON object matching this schema, no prose, no code fence:\n"
        + json.dumps(SCHEMA)
        + "\n\n"
        + user
    )
    r = subprocess.run(
        [claude, "-p", "--model", MODEL, "--output-format", "json", "--tools", ""],
        input=prompt, capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude -p failed: {r.stderr.strip()[:400]}")
    result = json.loads(r.stdout).get("result", "")
    start, end = result.find("{"), result.rfind("}")
    return json.loads(result[start : end + 1])


def write(agents: list[Agent], attempts: int = 2) -> Song:
    user = brief(agents)
    call = _via_sdk if _has_api_credentials() else _via_cli
    problems: list[str] = []
    for _ in range(attempts):
        prompt = user if not problems else user + "\n\nYour last draft had problems; fix them: " + "; ".join(problems)
        song = Song.from_dict(call(prompt))
        problems = song.problems()
        if not problems:
            return song
    raise RuntimeError("lyrics failed checks: " + "; ".join(problems))


def template(agents: list[Agent]) -> Song:
    """Offline fallback: no rhymes worth tweeting, but valid and specific."""
    roles = assign([a.id for a in agents])
    chorus = Section("chorus", ["All"], [
        "Doo-wop, the build is green",
        "Seven little agents on the team",
        "You were gone, we kept it clean",
        "Shipping while you're in a dream",
    ])
    sections = [Section("intro", ["All"], ["Bom bom, the terminals glow", "Seven voices, here we go"]), chorus]
    for a in agents:
        s = roles[a.id]
        lines = [f"I'm {s.name} on {a.project}, hear me sing"]
        lines += [f.replace("asked to: ", "they asked me to ")[:80] for f in a.facts[:2]]
        sections.append(Section("verse", [s.name], lines))
    sections += [chorus, Section("outro", ["All"], ["Bom bom, the work is done"])]
    credits = {roles[a.id].name: f"{a.project}: {a.facts[0][:60]}" for a in agents}
    return Song(title="Seven Agents Doo-Wop", sections=sections, credits=credits)
