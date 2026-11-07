# Dwarf directions (campaign scratch, 2026-11-06)

Throwaway scripts that made the four dwarf-choir styles (claymation, cinematic, 16-bit pixel art, felt puppets) for the X campaign. They are not part of the `choir` package.

Steps, all on fal unless noted:

1. `lineups.py`: one four-dwarf lineup per style (nano-banana-pro).
2. `portraits.py`: solo portraits made from each lineup (nano-banana-pro/edit).
3. `bakeoff.py`: lip-sync models tried on one dwarf. The results:
   - Kling burns garbled subtitles into the video.
   - MiniMax H3 is the best value.
   - OmniHuman 1.5 acts the most.
4. `renderall.py`: OmniHuman for the claymation style, H3 for the others.
5. `compose.py`: a 2×2 terminal-grid reel, with each dwarf singing its turn.

Group shots used HeyGen Video 1 image-to-video through Monid (`monid run -p heygen -e /v1/video/heygen-video-1-i2v`). It sings from the prompt in its own voice.

The scripts expect to run from the agent-choir venv with `FAL_KEY` set. Media is not committed.
