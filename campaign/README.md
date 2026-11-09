# How we made the 16-bit crew

Not part of the `choir` package; kept so you can see (and remix) how the dwarfs were made.

- `dwarfs/`: the first round. Four styles (claymation, cinematic, 16-bit, felt puppets) as fal images, then lip-synced video. See its README.
- `pixel/`: the sprites that ship in `choir/assets/sprites/`. `sprites.py` draws each singer with a closed, half-open and open mouth (an image-edit model, called through the Monid CLI); `bake.py` shrinks them to 96 px on one shared palette and keeps only the mouth different between frames.

The reel needs none of this: `choir reel` animates the shipped sprites locally from the loudness of each clip.
