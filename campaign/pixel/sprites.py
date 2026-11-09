"""Make the 16-bit crew: one portrait per singer, then mouth-open and mouth-half variants.

Uses OpenAI gpt-image-2.6-flare edit through Monid (about $0.06 per image).
Output: work/{Name}_{closed,half,open}.png
"""
import urllib.request
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import mon

def image(prompt, out, refs):
    d = mon.run("openai", "/v1/image/gpt-image-2.6-flare-edit",
                {"prompt": prompt, "size": "1024x1024", "quality": "high", "images": refs})
    url = d["output"]["image"]["download_link"]
    urllib.request.urlretrieve(url, out)
    with open(Path(__file__).parent / "work" / "cost.jsonl", "a") as f:
        f.write(json.dumps({"out": out.name, "cost": d["cost"]["value"]}) + "\n")
    return url

WORK = Path(__file__).parent / "work"; WORK.mkdir(exist_ok=True)
LINEUP = json.load(open(Path(__file__).resolve().parents[1] / "dwarfs" / "lineups.json"))["pixel"]
STYLE = ("16-bit SNES-era pixel art portrait, crisp hard-edged pixels, no anti-aliasing, limited palette, "
         "head and shoulders, centred, facing the viewer, face large, mouth gently CLOSED, "
         "flat solid very dark green background (#0f1f17) with nothing else in it. No text, no badge, no border. "
         "An ORIGINAL fantasy dwarf, not Disney, no pointed stocking cap. Same pixel style and palette as the reference crew.")
WHO = {
 "Merge": "the dwarf with the brass headlamp, golden-brown beard and mustard-yellow work jacket from the reference",
 "Rebase": "the huge old dwarf with the enormous braided white beard with blue beads and cobalt-blue cloak from the reference",
 "Deploy": "the woman dwarf with thick copper braids and rosy pink apron from the reference",
 "Lint": "the fussy dwarf with round spectacles, grey forked beard and moss-green waistcoat from the reference",
 "Docs": "a NEW woman dwarf in the same style: long black braid wrapped with a violet ribbon, a quill tucked behind her ear, violet scholar's hooded robe, warm calm eyes, no beard",
 "Patch": "a NEW young eager dwarf in the same style: short spiky ginger beard, a little bandage across his nose, bright orange overalls covered in sewn-on patches, big grin energy",
 "Grep": "a NEW wiry old dwarf in the same style: long thin silver mustache, sharp searching eyes, slate grey-teal hooded cloak, a tiny lantern clipped to his collar",
}

def portrait(name):
    p = WORK / f"{name}_closed.png"
    url = image(f"Make a solo portrait of {WHO[name]}. {STYLE}", p, refs=[LINEUP])
    return name, url

def mouths(item):
    name, url = item
    out = {}
    for tag, how in [("open", "wide open as if belting a long 'aah' note, teeth and tongue visible"),
                     ("half", "half open as if singing 'oh', a small oval")]:
        out[tag] = image(f"Edit this pixel art portrait. Change ONLY the mouth: make it {how}. Keep every other pixel, "
                         "the pose, framing, eyes, beard, clothes, colours and background exactly identical.",
                         WORK / f"{name}_{tag}.png", refs=[url])
    return name, out

if __name__ == "__main__":
    names = sys.argv[1:] or list(WHO)
    with ThreadPoolExecutor(7) as ex:
        urls = dict(ex.map(portrait, names))
        json.dump(urls, open(WORK / "closed_urls.json", "w"), indent=1)
        list(ex.map(mouths, urls.items()))
    print("done", names)
