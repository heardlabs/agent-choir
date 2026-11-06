import json
from pathlib import Path

import pytest

from choir import lyrics, providers, video, work
from choir.cast import MAX_AGENTS, assign
from choir.song import Section, Song

EX = Path(__file__).parent.parent / "examples" / "work.json"


def agents():
    return work.top_agents(work.from_json(EX))


def test_top_agents_sorted_and_capped():
    a = agents()
    assert [x.project for x in a][0] == "heard-v3"
    assert len(work.top_agents(a * 3)) == MAX_AGENTS


def test_scrub_removes_secrets_emails_urls_home():
    s = work.scrub("key sk-ant-abcdefghijklmnopqrstuv mail kelly@heard.dev at https://x.io/a in /home/kelly/p")
    assert "sk-ant" not in s and "@" not in s and "https" not in s and "/home/kelly" not in s


def test_assign_skips_beatboxer_and_caps():
    roles = assign(["a", "b"])
    assert roles["a"].name == "Merge" and all(r.name != "Grep" for r in roles.values())
    with pytest.raises(ValueError):
        assign([str(i) for i in range(MAX_AGENTS + 1)])


def test_template_song_is_valid():
    song = lyrics.template(agents())
    assert song.problems() == []


def test_banned_phrases_rejected():
    song = lyrics.template(agents())
    song.sections[0].lines.append("Heigh-ho we go")
    assert any("banned" in p for p in song.problems())


def test_unknown_singer_rejected():
    song = Song("t", [Section("chorus", ["Sneezy"], ["la"])])
    assert any("unknown singer" in p for p in song.problems())


def test_song_roundtrip(tmp_path):
    song = lyrics.template(agents())
    song.save(tmp_path / "s.json")
    assert Song.load(tmp_path / "s.json") == song


@pytest.mark.parametrize("key", list(providers.PROVIDERS))
def test_every_provider_builds_a_valid_payload(key):
    song = lyrics.template(agents())
    p = providers.PROVIDERS[key]
    payload = p.build(song)
    json.dumps(payload)
    assert p.cost(song) >= 0
    if key.startswith("minimax"):
        assert "[Chorus]" in payload["lyrics"] and 10 <= len(payload["prompt"]) <= 2000
    if key.startswith("lyria"):
        assert "no instruments" in payload["prompt"] and len(payload["prompt"]) <= 5000
    if key == "elevenlabs":
        secs = payload["composition_plan"]["sections"]
        assert len(secs) == len(song.sections)
        assert all(3000 <= s["duration_ms"] <= 120000 for s in secs)
        assert len(p.timings(song)) == len(song.sections) + 1
    if key == "ace-step":
        assert "[chorus]" in payload["lyrics"] and payload["tags"]


def test_section_times_cover_track():
    song = lyrics.template(agents())
    spans = video.section_times(song, 60.0, None)
    assert spans[0][0] == 0 and abs(spans[-1][1] - 60.0) < 1e-6
    pinned = providers.PROVIDERS["elevenlabs"].timings(song)
    spans = video.section_times(song, 50.0, pinned)
    assert abs(spans[-1][1] - 50.0) < 1e-6


def test_claude_transcript_parsing(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    recs = [
        {"type": "user", "cwd": "/home/x/repo-a", "origin": {"kind": "human"}, "message": {"content": "fix the flaky login test"}},
        {"type": "assistant", "cwd": "/home/x/repo-a", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/x/repo-a/login.test.ts"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "git commit -m 'wait for the cookie before asserting'"}},
            {"type": "text", "text": "Fixed: the test now waits for the session cookie."}]}},
    ]
    (proj / "abc123456.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
    [a] = work.from_claude(tmp_path, since=0)
    assert a.project == "repo-a"
    joined = " ".join(a.facts)
    assert "flaky login" in joined and "login.test.ts" in joined and "cookie" in joined


def test_video_renders(tmp_path):
    import subprocess
    wav = tmp_path / "a.wav"
    subprocess.run([video.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=6", str(wav)], check=True)
    song = lyrics.template(agents())
    out = video.render(song, wav, tmp_path / "o.mp4")
    assert out.exists() and out.stat().st_size > 10_000
    assert 5.5 < video.audio_seconds(out) < 6.5


def test_shell_noise_is_not_a_fact(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    recs = [{"type": "assistant", "cwd": "/r/x", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "git commit -m \"$msg\""}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "WT=~/a; until true; do :; done"}},
        {"type": "tool_use", "name": "Edit", "input": {"file_path": "/r/x/a.py"}}]}}]
    (proj / "s.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
    [a] = work.from_claude(tmp_path, since=0)
    joined = " ".join(a.facts)
    assert "$msg" not in joined and "WT=" not in joined and "until" not in joined


def test_long_verse_card_fits():
    song = Song("t", [Section("verse", ["Merge"], ["a long singable line about fixing the flaky login test again"] * 8)],
                credits={"Merge": "x" * 200})
    video.card(song, song.sections[0])  # must not raise; visual check is manual
