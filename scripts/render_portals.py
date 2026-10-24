#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Render original looping blue/red rift sprites using NumPy and Pillow.

No source images are used. Integer temporal frequencies make the turbulence
periodic, including the transition from the last frame back to the first.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
SIZE = (94, 154)
FRAMES = 8
DURATION = 0.4
VARIANTS = {
    'portal': (10, [[3, 17, 30], [5, 58, 81], [10, 114, 144],
                    [34, 180, 205], [139, 236, 245]]),
    'portal_rot': (798, [[32, 4, 2], [99, 13, 3], [180, 36, 4],
                        [241, 86, 9], [255, 191, 67]]),
}


def render(seed: int, variant: str, phase: float) -> Image.Image:
    """Render one phase (0..1), also accepting 1 for loop verification."""
    rng = np.random.default_rng(seed)
    scale = 3
    y, x = np.mgrid[:SIZE[1]*scale, :SIZE[0]*scale] / scale
    # An upright oval whose top leans right, matching the isometric scene.
    v = (y - 76) / 64
    u = (x - 46 + v * 10) / 30
    radius = np.sqrt(u*u + v*v)
    angle = np.arctan2(v, u)
    t = 2 * np.pi * (phase % 1)
    noise = np.zeros_like(u)
    fine = np.zeros_like(u)
    for octave, target in ((0, noise), (1, fine)):
        for _ in range(12):
            a, b, c = rng.uniform(0, 2*np.pi, 3)
            frequency = rng.uniform(5, 13) * (1 + octave * 2)
            speed = int(rng.integers(1, 4))
            target += np.sin(u * np.cos(a) * frequency
                             + v * np.sin(a) * frequency
                             + 1.3*np.sin(v*5 + b + t) + c - speed*t) / 12
    edge = radius + .12*noise + .045*fine
    body = np.clip((1-edge)/.32, 0, 1)
    filaments = (.5 + .5*np.sin(angle*9 + radius*24 - t*2 + noise*7))**5
    heat = np.clip(.28 + noise*.75 + fine*.35 + filaments*.33, 0, 1)
    # Wispy boundary, luminous currents, and a dim, translucent interior.
    alpha = body * np.clip(.55 + noise*.8 + fine*.45 + filaments*.35, 0, 1)
    halo = np.exp(-((radius-.87)/.16)**2)*.16
    alpha = np.clip(alpha + halo, 0, 1)
    margin = np.clip(np.minimum.reduce([x-3, y-3, SIZE[0]-4-x, SIZE[1]-4-y])/6, 0, 1)
    alpha *= margin*margin*(3-2*margin)
    palette = np.array(VARIANTS[variant][1])
    rgb = np.stack([np.interp(heat, np.linspace(0, 1, len(palette)), palette[:, c])
                    for c in range(3)], axis=-1)
    rgba = np.dstack([rgb, alpha*255]).astype('uint8')
    image = Image.fromarray(rgba).resize(SIZE, Image.Resampling.LANCZOS)
    pixels = np.array(image)
    pixels[pixels[:, :, 3] == 0] = 0
    return Image.fromarray(pixels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=90210)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'client/textures/illarion/items')
    parser.add_argument('--preview-dir', type=Path, default=ROOT/'particles/portal-preview')
    parser.add_argument('--write-visuals', action='store_true', help='Update item 10 and 798 visual definitions.')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for variant, (item_id, _) in VARIANTS.items():
        frames = [render(args.seed, variant, i/FRAMES) for i in range(FRAMES)]
        for i, frame in enumerate(frames):
            frame.save(args.output_dir/f'{variant}-{i}.png')
        previews(frames, args.preview_dir/variant, DURATION)
        if args.write_visuals:
            path = ROOT/f'client/data/illarion/visuals/items/item_{item_id}.json'
            visual = json.loads(path.read_text())
            visual.pop('texture', None)
            visual.update(type='animated', offsetX=3, offsetY=-19, surfaceOffsetY=0,
                          textures=[f'client/textures/illarion/items/{variant}-{i}.png' for i in range(FRAMES)],
                          duration=DURATION)
            path.write_text(json.dumps(visual, indent=2)+'\n')
    print(f'Rendered {FRAMES} frames per portal to {args.output_dir}')


if __name__ == '__main__':
    main()
