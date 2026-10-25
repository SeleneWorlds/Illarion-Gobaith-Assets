#!/usr/bin/env python3
"""Recolor Warspawn's painted red scroll binding; keep parchment pixels intact."""
from pathlib import Path
import colorsys
from PIL import Image

TEXTURES = Path(__file__).resolve().parents[1] / 'models/items/books/scroll/textures'
COLORS = {
    'black': (40, 42, 44),
    'green': (46, 185, 64),
    'orange': (230, 109, 27),
    'purple': (158, 53, 185),
    'red': (218, 36, 30),
    'white': (235, 235, 225),
    'yellow': (235, 207, 35),
}


def main():
    image = Image.open(TEXTURES / 'scroll_source.png').convert('RGBA')
    original = list(image.getdata())
    mask = []
    for r, g, b, _ in original:
        hue, saturation, value = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        mask.append((hue < 0.04 or hue > 0.97) and saturation > 0.65 and value > 0.3)
    assert any(mask), 'Missing red binding pixels'
    for name, color in COLORS.items():
        result = image.copy()
        # The original red channel carries the hand-painted highlight/shadow.
        result.putdata([tuple(round(channel * pixel[0]/255) for channel in color) + (pixel[3],)
                        if selected else pixel for pixel, selected in zip(original, mask)])
        assert all(a == b for a, b, selected in zip(original, result.getdata(), mask) if not selected)
        result.save(TEXTURES / f'scroll_{name}.png')
        print('Created', name, 'binding')


if __name__ == '__main__':
    main()
