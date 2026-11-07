import json
from concurrent.futures import ThreadPoolExecutor
from gen import lipsync, HERE, spent
P = json.load(open(HERE/"portraits.json"))
OMNI, H3 = "fal-ai/bytedance/omnihuman/v1.5", "minimax/h3-max/lip-sync/image-to-video"
DESC = {"clay": "a claymation dwarf", "cinematic": "a fantasy dwarf in a cinematic film", "pixel": "a 16-bit pixel art dwarf", "felt": "a felt puppet dwarf"}
jobs = [(k, s) for k in ["clay", "cinematic", "pixel", "felt"] for s in ["Merge", "Rebase", "Deploy", "Lint"] if not (HERE/k/f"{s}.mp4").exists()]
def go(j):
    k, s = j
    try:
        lipsync(OMNI if k == "clay" else H3, P[f"{k}/{s}"], s, HERE/k/f"{s}.mp4", prompt=f"{DESC[k]} singing joyfully a cappella to the camera")
        return f"{k}/{s} ok"
    except Exception as e: return f"{k}/{s} ERR {str(e)[:200]}"
with ThreadPoolExecutor(8) as ex:
    for r in ex.map(go, jobs): print(r)
print("spent", spent())
