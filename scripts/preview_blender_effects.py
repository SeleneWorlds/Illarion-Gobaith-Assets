#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Validate and preview the Blender particle renders (requires Pillow, NumPy)."""
import json
from pathlib import Path

from PIL import Image
from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
for name, gfx, size in [('stars', 41, (154, 153)), ('rain', 16, (144, 236)), ('blood', 13, (66, 58)), ('demfire', 5, (160, 223))]:
    visual = json.loads((ROOT / f'client/data/illarion/visuals/gfx/gfx_{gfx}.json').read_text())
    frames = [Image.open(ROOT / path).convert('RGBA') for path in visual['textures']]
    for frame in frames:
        assert frame.size == size
        alpha = frame.getchannel('A')
        w, h = size
        assert not alpha.crop((0, 0, w, 1)).getbbox(), name
        assert not alpha.crop((0, h - 1, w, h)).getbbox(), name
        assert not alpha.crop((0, 0, 1, h)).getbbox(), name
        assert not alpha.crop((w - 1, 0, w, h)).getbbox(), name
    assert any(frame.getchannel('A').getbbox() for frame in frames), f'{name}: empty animation'
    previews(frames, ROOT / 'particles' / f'{name}-preview', visual['duration'])
    print(f'{name}: {len(frames)} frames verified; previews written')
