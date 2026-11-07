import json
from concurrent.futures import ThreadPoolExecutor
from gen import image, HERE
L = json.load(open(HERE/"lineups.json"))
WHO = {"Merge": "the first dwarf (yellow jacket, headlamp, golden beard)", "Rebase": "the second dwarf (huge braided white beard, blue cloak)",
       "Deploy": "the third dwarf (copper braids, pink apron)", "Lint": "the fourth dwarf (spectacles, grey forked beard, green waistcoat)"}
def go(job):
    k, s = job
    prompt = (f"From this reference image, make a solo portrait of {WHO[s]} only. Exactly the same character design, materials and art style as the reference. "
              "Head and chest framing, centred, facing the camera, standing as if about to sing to the viewer, mouth gently closed, "
              "face large and clearly visible, same background setting softly out of focus. No text, no other characters.")
    if k == "pixel": prompt += " Keep it crisp 16-bit pixel art, large pixels."
    out = HERE / k / f"{s}.png"
    return f"{k}/{s}", image(prompt, out, refs=[L[k]], aspect="1:1")
jobs = [(k, s) for k in L for s in WHO]
with ThreadPoolExecutor(8) as ex: res = dict(ex.map(go, jobs))
json.dump(res, open(HERE/"portraits.json","w"), indent=1); print(len(res))
