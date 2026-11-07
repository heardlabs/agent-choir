import sys, json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from gen import image, HERE
CREW = ("a crew of four ORIGINAL fantasy dwarf characters standing side by side, each clearly different: "
 "1) MERGE: confident young dwarf with short golden-brown beard, mustard-yellow work jacket, brass headlamp; "
 "2) REBASE: huge old dwarf, enormous braided white beard with blue beads, deep cobalt-blue cloak, calm; "
 "3) DEPLOY: woman dwarf, thick copper braids pinned up, rosy pink leather apron, bright eyes, no beard; "
 "4) LINT: fussy dwarf with round spectacles and a jeweller's loupe, neat grey forked beard, moss-green waistcoat. "
 "Each wears a small glowing terminal badge. They are a cappella singers. "
 "Not Disney, not Snow White, no pointed stocking caps, no lantern-nosed cartoon look. ")
STYLES = {
 "clay": "Stop-motion claymation figurines, visible thumbprints and plasticine texture, miniature set of a mine whose walls are server racks with blinking LEDs, warm tungsten practical lights, shallow depth of field, Aardman-adjacent craft but original.",
 "cinematic": "Photoreal cinematic film still, epic fantasy dwarves in a stone forge-hall lit by the cold blue glow of many computer monitors and orange forge fire, 35mm anamorphic, rich detail in beards and leather.",
 "pixel": "16-bit pixel art sprites, SNES-era palette, crisp pixels, no anti-aliasing, dark terminal-green background with faint scanlines, characters shown front-facing, chunky readable silhouettes.",
 "felt": "Handmade felt hand-puppets with fuzzy fleece beards, foam bodies, ping-pong-ball eyes, hinged puppet mouths, on a tiny variety-show stage with a velvet curtain and old CRT monitors as props.",
}
def go(k):
    out = HERE / k / "lineup.png"; out.parent.mkdir(exist_ok=True)
    url = image(CREW + STYLES[k], out, aspect="16:9")
    return k, url
with ThreadPoolExecutor(4) as ex:
    res = dict(ex.map(go, STYLES))
json.dump(res, open(HERE/"lineups.json","w"), indent=1); print(res)
