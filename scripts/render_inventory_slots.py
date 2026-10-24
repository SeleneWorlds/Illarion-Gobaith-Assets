"""Generate native-size inventory diamonds without scaling source artwork.

Run with: python3 scripts/render_inventory_slots.py
Requires NumPy and Pillow. All distances below are in output pixels.
"""

from pathlib import Path

import numpy as np
from PIL import Image


OUTPUT = Path(__file__).resolve().parents[1] / "client/textures/illarion/ui"
WIDTH, HEIGHT = 131, 67
SAMPLES = 8


def smoothstep(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def render(highlight):
    # Evaluate the diamond analytically at subpixel positions. Average premultiplied
    # colors for coverage antialiasing, avoiding dark fringes on transparent edges.
    y, x = np.mgrid[: HEIGHT * SAMPLES, : WIDTH * SAMPLES]
    x = (x + 0.5) / SAMPLES - 0.5
    y = (y + 0.5) / SAMPLES - 0.5
    distance = (33 - abs(y - 33) - abs(x - 65) * 0.5) / np.sqrt(1.25)
    alpha = smoothstep(-0.5, 0.5, distance)
    border = np.array([54, 76, 107])
    inner = np.array([14, 22, 35])
    bevel = smoothstep(0.5, 2.1, distance)[..., None]
    rgb = border * (1 - bevel) + inner * bevel
    interior = smoothstep(2.2, 3.4, distance)[..., None]
    rgb *= 1 - interior
    if highlight:
        # A small, smooth fade from the recessed rim to the original pale fill.
        fill = smoothstep(2.8, 4.4, distance)[..., None]
        rgb = rgb * (1 - fill) + 207 * fill
    rgba = np.concatenate((rgb * alpha[..., None], alpha[..., None]), axis=-1)
    rgba = rgba.reshape(HEIGHT, SAMPLES, WIDTH, SAMPLES, 4).mean(axis=(1, 3))
    # Remove summation-order noise at half-integer rounding boundaries.
    rgba = np.round(rgba, 10)
    a = rgba[..., 3:4]
    rgb = np.divide(rgba[..., :3], a, out=np.zeros_like(rgba[..., :3]), where=a > 0)
    return Image.fromarray(np.rint(np.concatenate((rgb, a * 255), axis=-1)).astype("uint8"))


if __name__ == "__main__":
    for slot, highlight in ((0, False), (7, True)):
        path = OUTPUT / f"inv_slot-{slot}.png"
        render(highlight).save(path)
        print(path)
