#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Render a seeded particle burst; requires Pillow and NumPy.

Generate particle fields with per-effect canvas sizes and playback durations.
Output uses straight alpha for ordinary sprite compositing.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FRAMES = 11
SCALE = 3


VARIANTS = {
    "fireball": ((97, 102), 1.8),
    "elffire": ((97, 102), 1.2),
    "fizzle": ((89, 89), 0.6),
    "giftwolke": ((92, 85), 2.25),
}


def render(seed: int, variant: str = "fireball") -> list[Image.Image]:
    size, _ = VARIANTS[variant]
    poison = variant == "giftwolke"
    smoke = variant in ("fizzle", "giftwolke")
    count = 20 if poison else FRAMES
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:size[1] * SCALE, :size[0] * SCALE] / SCALE
    x, y = x - size[0] // 2, y - size[1] // 2
    # Persistent particles give coherent motion between animation frames.
    particles = [(rng.uniform(0, 2 * np.pi), rng.uniform(0.2, 1),
                  rng.uniform(2.5, 6), rng.uniform(0, 2 * np.pi))
                 for _ in range(90)]
    waves = [(rng.uniform(0.35, 1.1), rng.uniform(0, 2 * np.pi),
              rng.uniform(0, 2 * np.pi)) for _ in range(24)]
    frames = []
    for frame in range(count):
        t = frame / (count - 1)
        expansion = 3 + (18 if smoke else 21) * (1 - np.exp(-4 * t))
        envelope = np.sin(np.pi * t) ** 0.8
        density = np.zeros_like(x)
        turbulence = sum(np.sin(x * f * np.cos(a) + y * f * np.sin(a)
                                + phase + t * 8) for f, a, phase in waves) / 12
        for angle, speed, radius, phase in particles:
            distance = expansion * speed
            px = np.cos(angle) * distance + 1.8 * np.sin(phase + t * 5)
            py = np.sin(angle) * distance - (13 if smoke else 8) * t
            if poison:
                px += 2.5 * np.sin(phase + t * 7) * t
                py += 4 * t
            r = radius * (0.5 + 0.9 * np.sin(np.pi * t))
            if smoke:
                r *= 1 + 0.7 * t
            d = ((x - px) / r) ** 2 + ((y - py) / (r * 1.2)) ** 2
            density += np.exp(-d * 1.7) * (0.7 + 0.3 * np.sin(phase + t * 10))
        density *= np.clip(0.8 + turbulence * 0.9, 0, 1.4)
        heat = 1 - np.exp(-density * 0.7)
        heat *= (1 - t * 0.65)
        alpha = (1 - np.exp(-density * 1.5)) * envelope
        # Low-opacity halo surrounds the detailed flame without a hard outline.
        halo = np.exp(-(x*x + (y + 5*t)**2) / (expansion * 1.15)**2)
        alpha = np.clip(alpha + halo * envelope * 0.12, 0, 1)
        if smoke:
            # Scattering puffs have no emissive halo and lose opacity as they spread.
            alpha = (1 - np.exp(-density * 0.55)) * envelope * (1 - 0.65 * t)
            # Dissipate the outer wisps before they reach the smaller canvas edge.
            edge = np.clip((40 - np.maximum(np.abs(x), np.abs(y))) / 7, 0, 1)
            if poison:
                edge = np.clip(np.minimum(size[0] / 2 - 4 - np.abs(x),
                                          size[1] / 2 - 4 - np.abs(y)) / 7, 0, 1)
                alpha *= 1.25
            alpha *= edge * edge * (3 - 2 * edge)
            heat = np.clip(0.3 + 0.45 * heat + turbulence * 0.18, 0, 1)
        stops = np.array([0, 0.18, 0.4, 0.65, 0.85, 1])
        palette = np.array([[100, 19, 8], [188, 37, 7], [244, 80, 8],
                            [255, 159, 26], [255, 224, 112], [255, 249, 207]])
        if variant == "elffire":
            palette = np.array([[10, 34, 88], [15, 80, 155], [25, 145, 220],
                                [74, 206, 250], [160, 240, 255], [235, 253, 255]])
        elif poison:
            fresh = np.array([[16, 37, 12], [27, 67, 17], [46, 115, 25],
                              [83, 166, 39], [139, 198, 63], [189, 222, 105]])
            aged = np.array([[33, 34, 10], [61, 65, 15], [100, 110, 22],
                             [146, 157, 33], [186, 194, 55], [215, 220, 91]])
            palette = fresh * (1 - t) + aged * t
        elif smoke:
            palette = np.array([[48, 51, 57], [66, 70, 77], [94, 100, 108],
                                [135, 141, 149], [172, 178, 184], [203, 208, 213]])
        rgb = np.stack([np.interp(heat, stops, palette[:, c]) for c in range(3)], -1)
        rgba = np.dstack((rgb, alpha * 255)).astype('uint8')
        rgba[rgba[:, :, 3] == 0] = 0
        im = Image.fromarray(rgba).resize(size, Image.Resampling.LANCZOS)
        frames.append(im)
    return frames


def previews(frames: list[Image.Image], directory: Path, duration: float = 1.8) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    size = frames[0].size
    sheet = Image.new('RGB', (size[0] * len(frames), size[1] + 18), '#252a30')
    draw = ImageDraw.Draw(sheet)
    animation = []
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * size[0], 0), frame)
        draw.text((i * size[0] + 4, size[1]), str(i), fill='white')
        bg = Image.new('RGB', size, '#252a30')
        bg.paste(frame, (0, 0), frame)
        animation.append(bg.resize((size[0] * 3, size[1] * 3), Image.Resampling.NEAREST))
    sheet.save(directory / 'contact-sheet.png')
    animation[0].save(directory / 'preview.gif', save_all=True,
                      append_images=animation[1:], duration=[round((i + 1) * duration * 100 / len(frames)) * 10
                                - round(i * duration * 100 / len(frames)) * 10
                                for i in range(len(frames))], loop=0, disposal=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=VARIANTS, default='fireball')
    parser.add_argument('--seed', type=int, default=90210)
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT / 'client/textures/illarion/effects')
    parser.add_argument('--preview-dir', type=Path)
    args = parser.parse_args()
    frames = render(args.seed, args.variant)
    preview_dir = args.preview_dir or ROOT / 'particles' / f'{args.variant}-preview'
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        frame.save(args.output_dir / f'{args.variant}-{i}.png')
    previews(frames, preview_dir, VARIANTS[args.variant][1])
    print(f'Rendered {len(frames)} frames to {args.output_dir}')


if __name__ == '__main__':
    main()
