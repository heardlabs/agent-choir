import json
from concurrent.futures import ThreadPoolExecutor
from gen import lipsync, HERE, spent
P = json.load(open(HERE/"portraits.json"))
M = {"kling-std": "fal-ai/kling-video/ai-avatar/v2/standard", "kling-pro": "fal-ai/kling-video/ai-avatar/v2/pro",
     "omni": "fal-ai/bytedance/omnihuman/v1.5", "h3": "minimax/h3-max/lip-sync/image-to-video"}
(HERE/"bakeoff").mkdir(exist_ok=True)
def go(k):
    try:
        return k, str(lipsync(M[k], P["clay/Merge"], "Merge", HERE/"bakeoff"/f"{k}.mp4", prompt="a claymation dwarf singing joyfully a cappella, subtle head bob"))
    except Exception as e: return k, f"ERR {e}"
with ThreadPoolExecutor(4) as ex: print(dict(ex.map(go, M)))
print("spent", spent())
