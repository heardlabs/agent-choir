import json
import subprocess
from pathlib import Path

import pytest

from choir import agents, audio, cli, config, core, ledger, providers, reel, summarize
from choir.agents import Turn
from choir.cast import CAST, NAMES


def tone(path: Path, secs=3.0, lead_silence=1.0):
    subprocess.run([audio.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"anullsrc=r=44100:cl=mono:d={lead_silence}", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={secs}", "-filter_complex", "[0][1]concat=n=2:v=0:a=1",
                    str(path)], check=True)
    return path


# --- hooks ---------------------------------------------------------------

def test_claude_hook_payload_uses_terminal_when_known():
    p = {"session_id": "s1", "cwd": "/x/billing-api", "last_assistant_message": "Fixed it."}
    t = agents.from_claude_hook(p, {"TMUX_PANE": "%3"})
    assert (t.agent, t.project, t.message) == ("TMUX_PANE:%3", "billing-api", "Fixed it.")
    assert agents.from_claude_hook(p, {}).agent == "claude:s1"


def test_codex_notify_payload():
    p = {"type": "agent-turn-complete", "thread-id": "t9", "cwd": "/x/web", "last-assistant-message": "Done."}
    t = agents.from_codex_notify(p, {})
    assert (t.agent, t.project, t.message, t.source) == ("codex:t9", "web", "Done.", "codex")
    assert agents.from_codex_notify({"type": "other"}, {}) is None


def test_hook_never_raises_on_garbage(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("not json"))
    cli.hook("claude", None)  # logs, does not raise
    cli.hook("codex", "{bad")


def test_hook_skips_when_stop_hook_active(monkeypatch):
    called = []
    monkeypatch.setattr(cli, "_detach", lambda *a: called.append(a))
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps({"stop_hook_active": True})))
    cli.hook("claude", None)
    assert not called


# --- seats ---------------------------------------------------------------

def test_each_terminal_keeps_its_own_singer():
    a, b = Turn("t:a", "api", "", "x"), Turn("t:b", "web", "", "x")
    sa, sb = agents.singer_for(a), agents.singer_for(b)
    assert sa.name != sb.name
    assert agents.singer_for(a).name == sa.name


def test_quiet_terminal_releases_its_singer():
    agents.singer_for(Turn("t:a", "api", "", "x"), now=0)
    s = agents.singer_for(Turn("t:b", "web", "", "x"), now=agents.RELEASE_S + 10)
    assert s.name == NAMES[0]


def test_more_terminals_than_singers_reuses_quietest():
    for i in range(len(CAST)):
        agents.singer_for(Turn(f"t:{i}", "p", "", "x"), now=100 + i)
    s = agents.singer_for(Turn("t:new", "p", "", "x"), now=200)
    assert s.name == NAMES[0]


def test_project_pin_wins():
    assert agents.singer_for(Turn("t:a", "api", "", "x"), pins={"api": "Rebase"}).name == "Rebase"


# --- summarizing ---------------------------------------------------------

def test_plain_summary_is_short_and_singable():
    msg = "## Done\nFixed the `limiter.ts` bug in https://x.io so **all 214 tests** pass. Next I will deploy."
    line = summarize.summarize(msg, "plain")
    assert "http" not in line and "`" not in line and "*" not in line and "#" not in line
    assert "Next" not in line
    assert len(line.split()) <= summarize.MAX_WORDS


def test_banned_reference_phrases_are_removed():
    assert "heigh" not in summarize.finish("Heigh-ho, tests are green").lower()


def test_summarizer_falls_back_to_plain(monkeypatch):
    monkeypatch.setattr(summarize, "_anthropic", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    assert summarize.summarize("Shipped the docs site today. More later.", "anthropic") == "Shipped the docs site today"


def test_plain_cuts_long_sentence_at_a_clause_break():
    msg = "I updated quota.ts so the daily quota resets on the user's local day instead of UTC midnight. All 214 tests pass."
    assert summarize.plain(msg) == "All 214 tests pass"
    msg = "I updated the quota code so the daily quota resets on the local day instead of UTC midnight for everyone."
    assert summarize.plain(msg) == "I updated the quota code"


# --- providers -----------------------------------------------------------

@pytest.mark.parametrize("key", list(providers.PROVIDERS))
def test_every_provider_builds_a_request(key):
    p = providers.PROVIDERS[key]
    payload = p.request("I fixed the login test", CAST[1], "a cappella", 6.0)
    json.dumps(payload)
    assert p.cost(6.0) >= 0
    text = json.dumps(payload)
    assert "I fixed the login test" in text
    if "elevenlabs" in key:
        assert payload["music_length_ms"] == 6000
    if key == "fal:ace-step":
        assert payload["seed"] == CAST[1].seed and payload["duration"] == 6


def test_clip_seconds_bounds():
    assert providers.clip_seconds("hi", 12) == 4.0
    assert providers.clip_seconds("word " * 40, 12) == 12


# --- audio + full path ---------------------------------------------------

def test_finish_trims_silence_caps_length_and_pans(tmp_path):
    src = tone(tmp_path / "in.wav", secs=20, lead_silence=1.5)
    out = audio.finish(src, tmp_path / "out.wav", pan=-1.0, max_s=6)
    assert 5.5 < audio.seconds(out) <= 6.1
    assert audio.pan_gains(0)[0] == pytest.approx(audio.pan_gains(0)[1])


class FakeProvider(providers.Provider):
    def sing(self, line, singer, style, seconds, dest, log=None):
        return tone(dest.with_suffix(".src.wav"), secs=seconds).rename(dest)


@pytest.fixture
def fake(monkeypatch):
    p = FakeProvider("fake", "PATH", "test", lambda *a: {}, lambda s: 0.5)
    monkeypatch.setitem(providers.PROVIDERS, "fake", p)
    return config.Settings(provider="fake", summarizer="plain", daily_budget_usd=1.0)


def test_perform_records_and_caches(fake):
    t = Turn("t:a", "api", "I fixed the flaky login test today.", "cli")
    e1 = core.perform(t, fake, play=False, echo=lambda *_: None)
    assert e1["singer"] == NAMES[0] and e1["cost"] == 0.5
    assert (ledger.clips_dir() / e1["clip"]).exists()
    e2 = core.perform(t, fake, play=False, echo=lambda *_: None)
    assert e2["clip"] == e1["clip"] and e2["cost"] == 0.0  # cached, free


def test_budget_stops_singing(fake):
    lines = ["one two three four five", "six seven eight nine ten", "eleven twelve thirteen fourteen"]
    got = [core.perform(Turn("t:a", "api", l, "cli"), fake, play=False, echo=lambda *_: None) for l in lines]
    assert got[0] and got[1] and got[2] is None  # $0.50 each, $1.00 a day


def test_short_messages_and_mute_skip(fake):
    assert core.perform(Turn("t:a", "api", "Done.", "cli"), fake, play=False) is None
    fake.muted = True
    assert core.perform(Turn("t:a", "api", "I fixed the login test today", "cli"), fake, play=False) is None


def test_missing_key_is_reported_not_raised(monkeypatch):
    s = config.Settings(provider="fal:lyria3", summarizer="plain")
    msgs = []
    assert core.perform(Turn("t:a", "api", "I fixed the login test today", "cli"), s, play=False, echo=msgs.append) is None
    assert "FAL_KEY" in msgs[0]


def test_reel_renders_turns_and_round(fake, tmp_path):
    fake.daily_budget_usd = 10
    es = [core.perform(Turn(f"t:{i}", f"proj{i}", f"line number {i} is sung here", "cli"), fake, play=False,
                       echo=lambda *_: None) for i in range(3)]
    out = reel.render(es, tmp_path / "r.mp4")
    assert out.stat().st_size > 10_000
    out2 = reel.render(es, tmp_path / "r2.mp4", stagger=1.0)
    assert audio.seconds(out2) < audio.seconds(out)


# --- install -------------------------------------------------------------

def test_install_claude_merges_and_is_idempotent(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other"}]}]}}))
    cli.install_claude(p)
    data = json.loads(p.read_text())
    assert data["model"] == "x" and len(data["hooks"]["Stop"]) == 2
    assert data["hooks"]["Stop"][1]["hooks"][0]["async"] is True
    assert cli.install_claude(p) == "already installed"


def test_install_codex_puts_notify_at_top_level(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('model = "gpt"\n[profiles.x]\nmodel = "y"\n')
    cli.install_codex(p)
    import tomllib
    data = tomllib.loads(p.read_text())
    assert data["notify"][-2:] == ["hook", "codex"]
    p.write_text('notify = ["mine"]\n')
    assert "already has a notify" in cli.install_codex(p)
