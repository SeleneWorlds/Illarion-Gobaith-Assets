#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Render tile-filling, looping stationary fire and ice flames; NumPy/Pillow."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIZE = (128, 224)
GROUND_Y = SIZE[1] - 32
FRAMES = 5
SCALE = 3
PALETTES = {
    'flamme': [[113, 16, 2], [222, 49, 3], [255, 126, 8],
               [255, 211, 53], [255, 250, 186]],
    'ice': [[15, 47, 133], [24, 111, 206], [58, 185, 244],
            [145, 234, 255], [232, 253, 255]],
}


def render(variant: str, phase: float, seed: int = 90210) -> Image.Image:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:SIZE[1]*SCALE, :SIZE[0]*SCALE] / SCALE
    t = (phase % 1) * 2 * np.pi
    # Keep the 128×64 ground diamond anchored 32 pixels above the bottom.
    diamond = np.abs(x-64)/64 + np.abs(y-GROUND_Y)/32
    base = np.clip((1-diamond)*16, 0, 1)
    density = base * .8
    # Composite back to front, with flames rooted throughout the tile surface.
    roots = []
    for u in np.linspace(-.9, .9, 9):
        for v in np.linspace(-.9, .9, 9):
            roots.append((64+32*(u-v), GROUND_Y+16*(u+v), *rng.random(3)))
    for px, py, a, b, c in sorted(roots, key=lambda root: root[1]):
        # Tall tongues rise roughly two tile heights (128 pixels).
        height = 84 + 76*a
        h = (py-y)/height
        sway = (np.sin(h*8-t+b*6.28)*3 + np.sin(h*17-2*t+c*6.28))*h
        width = (6+3*b)*np.maximum(1-h, 0)**.75 + .3
        profile = 1-((x-px-sway)/width)**2-h*.7
        turbulence = .16*np.sin(x*.7+y*.3-2*t+c*6.28)
        plume = np.clip(profile+turbulence, 0, 1)
        plume *= np.clip((1-h)*6, 0, 1)*np.clip((h+.03)*20, 0, 1)
        density = density*(1-plume*.8)+plume
    heat = np.clip(density*.85 + base*.15, 0, 1)
    palette = np.array(PALETTES[variant])
    rgb = np.stack([np.interp(heat, np.linspace(0, 1, len(palette)),
                              palette[:, c]) for c in range(3)], -1)
    alpha = np.clip(density*2, 0, 1)
    rgba = np.dstack([rgb, alpha*255]).astype('uint8')
    rgba[rgba[:, :, 3] == 0] = 0
    return Image.fromarray(rgba).resize(SIZE, Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT/'client/textures/illarion/items/effects/fields')
    parser.add_argument('--update-visuals', action='store_true')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for variant, item_id in [('flamme', 359), ('ice', 360)]:
        for index in range(FRAMES):
            render(variant, index/FRAMES).save(args.output_dir/f'{variant}-{index}.png')
        if args.update_visuals:
            path = ROOT/f'client/data/illarion/visuals/items/item_{item_id}.json'
            visual = json.loads(path.read_text())
            # Anchor at the tile center, 32 pixels above the canvas bottom.
            visual.update(offsetX=0, offsetY=-32)
            path.write_text(json.dumps(visual, indent=2)+'\n')
        print(f'Rendered {FRAMES} stationary {variant} frames')


if __name__ == '__main__':
    main()
