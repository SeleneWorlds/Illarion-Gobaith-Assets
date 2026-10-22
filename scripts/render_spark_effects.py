#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Seeded teleport sparkles and red splash; requires Pillow and NumPy."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = {'scotty': (53, (104, 172)), 'splash': (45, (224, 194))}
SCALE = 3
FRAMES = 15
DURATION = 1.5


def render(seed: int, variant: str) -> list[Image.Image]:
    _, size = VARIANTS[variant]
    rng = np.random.default_rng(seed)
    count = 180 if variant == 'scotty' else 650
    particles = rng.random((count, 7))
    frames = []
    for index in range(FRAMES):
        t = index / (FRAMES - 1)
        envelope = np.sin(np.pi * t) ** 0.7
        image = Image.new('RGBA', (size[0] * SCALE, size[1] * SCALE))
        draw = ImageDraw.Draw(image)
        for a, b, c, phase, speed, radius, brightness in particles:
            if variant == 'scotty':
                twinkle = (0.5 + 0.5 * np.sin(phase * 2*np.pi + t * 19)) ** 3
                if b > envelope or twinkle < 0.08:
                    continue
                angle = a * 2*np.pi + t * 5
                x = 52 + np.cos(angle) * (7 + 23 * c)
                y = 15 + ((b - t * (0.3 + speed * 0.4)) % 1) * 140
                r = (0.6 + radius * 1.3) * (0.5 + twinkle)
                alpha = int(255 * envelope * (0.35 + 0.65 * twinkle))
                color = (125 + int(100 * brightness), 220 + int(35 * brightness), 255, alpha)
                x, y, r = x*SCALE, y*SCALE, r*SCALE
                draw.ellipse((x-r*.4, y-r*.4, x+r*.4, y+r*.4), fill=color)
                draw.polygon([(x-r*2,y), (x-r*.23,y-r*.23), (x,y-r*2.8),
                              (x+r*.23,y-r*.23), (x+r*2,y), (x+r*.23,y+r*.23),
                              (x,y+r*2.8), (x-r*.23,y+r*.23)], fill=color)
            else:
                angle = a * 2*np.pi
                distance = (8 + 91 * t) * np.sqrt(b)
                x = 112 + np.cos(angle) * distance
                y = 75 + np.sin(angle) * distance * 0.65 + 42*t*t - 15*t
                r = (0.45 + radius * 0.9) * (1 - 0.35*t)
                alpha = int(255 * envelope * (1 - 0.45*t) * (0.45 + 0.55*brightness))
                color = (190 + int(65 * brightness), 65 + int(75 * c), 60 + int(65 * c), alpha)
                x, y, r = x*SCALE, y*SCALE, r*SCALE
                draw.ellipse((x-r, y-r*(1+speed), x+r, y+r*(1+speed)), fill=color)
        if variant == 'scotty':
            # Faint bloom around the sharp star silhouettes, with straight alpha output.
            glow = image.filter(ImageFilter.GaussianBlur(2*SCALE))
            glow.putalpha(glow.getchannel('A').point(lambda a: int(a * 0.45)))
            image = Image.alpha_composite(glow, image)
        image = image.resize(size, Image.Resampling.LANCZOS)
        frames.append(image)
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=VARIANTS, required=True)
    parser.add_argument('--seed', type=int, default=90210)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'client/textures/illarion/effects')
    parser.add_argument('--preview-dir', type=Path)
    args = parser.parse_args()
    frames = render(args.seed, args.variant)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        frame.save(args.output_dir / f'{args.variant}-{i}.png')
    directory = args.preview_dir or ROOT/'particles'/f'{args.variant}-preview'
    previews(frames, directory, DURATION)
    print(f'Rendered {len(frames)} {args.variant} frames')


if __name__ == '__main__':
    main()
