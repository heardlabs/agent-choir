"""Scratch generator for the dwarf directions. Run with the agent-choir venv."""
import base64, json, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, "/home/kelly/projects/agent-choir")
from choir.providers import fal
from choir import audio

HERE = Path(__file__).parent
CLIPS = Path.home() / ".local/state/agent-choir/clips"
COST = HERE / "cost.jsonl"

CLIP = {  # singer -> (clip, line)
    "Merge": ("0a8f6f80763725c4.wav", "Fixed the midnight rate limiter bug, all two hundred tests pass"),
    "Rebase": ("c97a644c4f1673b9.wav", "The pricing page loads in one second now, down from three"),
    "Deploy": ("6e7a0a1cd8b17e6d.wav", "I wrote the hotkey guide and fixed eleven broken links"),
    "Lint": ("2beae21ab3a49321.wav", "I need your okay before I ship the release tonight"),
}


def log(model, cost, note):
    with open(COST, "a") as f:
        f.write(json.dumps({"ts": time.time(), "model": model, "cost": cost, "note": note}) + "\n")


def spent():
    return sum(json.loads(l)["cost"] for l in open(COST)) if COST.exists() else 0.0


def data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def mono_mp3(singer: str) -> Path:
    out = HERE / "audio" / f"{singer}.mp3"
    out.parent.mkdir(exist_ok=True)
    if not out.exists():
        subprocess.run([audio.ffmpeg(), "-nostdin", "-y", "-loglevel", "error", "-i", str(CLIPS / CLIP[singer][0]),
                        "-ac", "1", "-ar", "44100", "-b:a", "128k", str(out)], check=True, stdin=subprocess.DEVNULL)
    return out


def image(prompt: str, out: Path, refs: list[str] | None = None, aspect="1:1") -> str:
    """Returns the hosted URL; saves to out."""
    if refs:
        model, payload = "fal-ai/nano-banana-pro/edit", {"prompt": prompt, "image_urls": refs, "aspect_ratio": aspect}
    else:
        model, payload = "fal-ai/nano-banana-pro", {"prompt": prompt, "aspect_ratio": aspect}
    r = fal.run(model, payload)
    url = r["images"][0]["url"]
    fal.download(url, out)
    log(model, 0.15, out.name)
    return url


def lipsync(model: str, image_url: str, singer: str, out: Path, prompt: str = "") -> Path:
    a = mono_mp3(singer)
    secs = audio.seconds(a)
    payload = {"image_url": image_url, "audio_url": upload(a, "audio/mpeg")}
    if prompt:
        payload["prompt"] = prompt
    if "omnihuman" in model:
        payload["resolution"] = "720p"
    if "h3-max" in model:
        payload["enable_transcription"] = False
    t = time.time()
    r = fal.run(model, payload, timeout_s=1500)
    fal.download(r["video"]["url"], out)
    rate = {"omnihuman": 0.16, "ai-avatar/v2/pro": 0.115, "ai-avatar/v2/standard": 0.0562, "h3-max": 0.05, "fabric": 0.08}
    per = next(v for k, v in rate.items() if k in model)
    log(model, round(per * secs, 3), f"{out.name} {time.time()-t:.0f}s")
    return out


def upload(path: Path, mime: str) -> str:
    import urllib.request
    req = urllib.request.Request("https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3", method="POST",
        data=json.dumps({"content_type": mime, "file_name": path.name}).encode(),
        headers={"Authorization": f"Key {fal._key()}", "Content-Type": "application/json", "User-Agent": fal.UA})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    put = urllib.request.Request(d["upload_url"], data=path.read_bytes(), method="PUT", headers={"Content-Type": mime})
    urllib.request.urlopen(put, timeout=120).read()
    return d["file_url"]
