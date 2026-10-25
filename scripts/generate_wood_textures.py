#!/usr/bin/env python3
"""Derive reusable wood colors from CC0 Textures Wood 050 (no generated imagery)."""
import argparse
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
WOOD = ROOT / 'models/materials/wood'
# Shadow and highlight colors retain the source's fine grain at different tones.
PALETTES = {
    'conifer': ('#846039', '#f1d6a0'),
    'cherry': ('#593023', '#c88760'),
    'naldor': ('#271b15', '#806044'),
    'apple': ('#69452a', '#c7a071'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Optional original Wood050_4K-JPG directory')
    args = parser.parse_args()
    WOOD.mkdir(parents=True, exist_ok=True)
    if args.source:
        for source, target in [('Color', 'source_color.jpg'), ('Roughness', 'roughness.jpg'), ('NormalGL', 'normal_gl.jpg')]:
            with Image.open(args.source / f'Wood050_4K_{source}.jpg') as image:
                image = image.resize((2048, 2048), Image.Resampling.LANCZOS)
                image.save(WOOD / target, quality=95, subsampling=0)
    with Image.open(WOOD / 'source_color.jpg') as image:
        grain = ImageOps.autocontrast(ImageOps.grayscale(image), cutoff=1)
    for name, (dark, light) in PALETTES.items():
        ImageOps.colorize(grain, dark, light).save(WOOD / f'{name}_color.jpg', quality=95, subsampling=0)
        print(f'Created {name} wood')


if __name__ == '__main__':
    main()
