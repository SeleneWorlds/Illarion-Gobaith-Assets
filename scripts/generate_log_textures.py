#!/usr/bin/env python3
"""Prepare reusable CC0 Bark 007 / Tree End 001 textures in the wood palettes."""
import argparse
from pathlib import Path
from PIL import Image, ImageColor, ImageOps
from generate_wood_textures import PALETTES

ROOT = Path(__file__).resolve().parents[1]
WOOD = ROOT / 'models/materials/wood'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bark-source', type=Path)
    parser.add_argument('--end-source', type=Path)
    args = parser.parse_args()
    for kind, source, stem in [('bark', args.bark_source, 'Bark007'), ('end', args.end_source, 'TreeEnd001')]:
        if source:
            for suffix, name in [('Color', 'source_color'), ('Roughness', 'roughness'), ('NormalGL', 'normal_gl')]:
                with Image.open(source / f'{stem}_4K_{suffix}.jpg') as image:
                    image.resize((2048, 2048), Image.Resampling.LANCZOS).save(WOOD / f'{kind}_{name}.jpg', quality=95, subsampling=0)
        with Image.open(WOOD / f'{kind}_source_color.jpg') as image:
            # Ignore the black background outside the photographed cut end
            # when finding the useful grain range.
            sample = image.crop((350, 350, 1698, 1698)) if kind == 'end' else image
            histogram = ImageOps.grayscale(sample).histogram()
            total = sum(histogram)
            cumulative = 0
            low, high = 0, 255
            for value, count in enumerate(histogram):
                cumulative += count
                if cumulative <= total * 0.02: low = value
                if cumulative < total * 0.98: high = value
            gray = ImageOps.grayscale(image)
            gray = gray.point([max(0, min(255, round((v-low)*255/max(1, high-low)))) for v in range(256)])
        for wood, (dark, light) in PALETTES.items():
            if kind == 'bark':
                # Bark is darker and less saturated than the exposed wood.
                def bark_color(color):
                    rgb = ImageColor.getrgb(color)
                    mean = sum(rgb)/3
                    return tuple(round((v*0.40 + mean*0.60)*0.95) for v in rgb)
                dark, light = bark_color(dark), bark_color(light)
            ImageOps.colorize(gray, dark, light).save(WOOD / f'{wood}_{kind}_color.jpg', quality=95, subsampling=0)
            print(f'Created {wood} {kind}')


if __name__ == '__main__':
    main()
