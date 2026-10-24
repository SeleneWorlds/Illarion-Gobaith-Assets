#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Render original, glossy elemental drops with NumPy and Pillow; no image inputs."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
# Preserve the existing cropped canvases and item placement.
ELEMENTS = {
    "water": ((15, 22), (24, 118, 214)),
    "fire": ((17, 22), (244, 92, 14)),
    "earth": ((17, 22), (73, 145, 40)),
    "air": ((19, 22), (153, 206, 222)),
}


def render(element: str) -> Image.Image:
    size, color = ELEMENTS[element]
    scale = 8
    w, h = size
    mask = Image.new("L", (w * scale, h * scale))
    # A pointed tip flowing into a round belly, sampled as cubic Bezier curves.
    segments = [
        ((.5, .035), (.46, .26), (.075, .47), (.075, .67)),
        ((.075, .67), (.075, 1.07), (.925, 1.07), (.925, .67)),
        ((.925, .67), (.925, .47), (.54, .26), (.5, .035)),
    ]
    points = []
    for curve in segments:
        for t in np.linspace(0, 1, 100):
            p = sum(np.array(curve[i]) * weight for i, weight in enumerate(
                ((1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t*t, t**3)))
            points.append((p[0] * (w*scale-1), p[1] * (h*scale-1)))
    ImageDraw.Draw(mask).polygon(points, fill=255)
    y, x = np.mgrid[0:h*scale, 0:w*scale].astype(float)
    x /= w*scale
    y /= h*scale
    body = np.exp(-(((x-.42)/.39)**2 + ((y-.58)/.53)**2))
    edge = np.clip(1 - ((x-.5)/.46)**2, 0, 1)
    light = .30 + .60 * body + .16 * edge
    rgb = np.array(color)[None, None, :] * light[:, :, None]
    # Cool reflected light along the lower right edge; broad upper left gloss.
    rim = np.exp(-(((x-.76)/.085)**2 + ((y-.76)/.19)**2))
    gloss = np.exp(-(((x-.33)/.085)**2 + ((y-.53)/.14)**2))
    pin = np.exp(-(((x-.38)/.045)**2 + ((y-.40)/.055)**2))
    rgb += rim[:, :, None] * np.array((64, 89, 95))
    highlight = np.clip(.85*gloss + .65*pin, 0, .96)
    rgb = rgb * (1-highlight[:, :, None]) + 255*highlight[:, :, None]
    if element == "fire":
        core = np.exp(-(((x-.53)/.20)**2 + ((y-.72)/.23)**2))
        rgb += core[:, :, None] * np.array((42, 97, 7))
    elif element == "earth":
        # Subtle mineral facets inside the shared droplet silhouette.
        facet = np.clip(1-abs(x-(.58-.25*(y-.5)))/.035, 0, 1)
        rgb += (facet * np.exp(-((y-.7)/.21)**2))[:, :, None] * np.array((22, 29, 9))
    elif element == "air":
        swirl = np.exp(-((y-(.70+.055*np.sin(x*10)))/.025)**2)
        rgb += (swirl*np.exp(-((x-.5)/.30)**2))[:, :, None]*32
    rgba = np.dstack((np.uint8(np.clip(rgb, 0, 255)), np.asarray(mask)))
    return Image.fromarray(rgba).resize(size, Image.Resampling.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "client/textures/illarion/items")
    parser.add_argument("--preview", type=Path, help="Optional enlarged comparison PNG")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    preview = Image.new("RGB", (320, 144), (34, 38, 46))
    draw = ImageDraw.Draw(preview)
    for i, element in enumerate(ELEMENTS):
        sprite = render(element)
        path = args.output_dir / f"pure_{element}.png"
        sprite.save(path)
        print(path)
        enlarged = sprite.resize((sprite.width*4, sprite.height*4), Image.Resampling.NEAREST)
        preview.paste(enlarged, (i*80+(80-enlarged.width)//2, 12), enlarged)
        draw.text((i*80+20, 112), element, fill="white")
    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        preview.save(args.preview)


if __name__ == "__main__":
    main()
