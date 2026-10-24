"""Render selection and action markers analytically at their native sizes.

Run: python3 scripts/render_selection_markers.py (requires NumPy and Pillow).
No input artwork is used. Dimensions and radii preserve the UI footprints.
"""

from pathlib import Path

import numpy as np
from PIL import Image


OUTPUT = Path(__file__).resolve().parents[1] / "client/textures/illarion/ui"
SAMPLES = 8
SIZES = {
    "select_map": (141, 78),
    "select_char": (133, 74),
    "menu_select": (133, 135),
    "magic_select": (99, 102),
    "mark_fight": (234, 123),
    "mark_use": (234, 123),
}


def smoothstep(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def render(name):
    width, height = SIZES[name]
    y, x = np.mgrid[: height * SAMPLES, : width * SAMPLES]
    x = (x + 0.5) / SAMPLES - width / 2
    y = (y + 0.5) / SAMPLES - height / 2
    color = (251, 247, 175)
    if name == "select_map":
        # Original diamond is centered one pixel above the canvas midpoint.
        distance = abs((abs(x) / 64 + abs(y + 1) / 33 - 1) * 33 / np.sqrt(1.0 + (33 / 64) ** 2))
        alpha = 0.75 * (1 - smoothstep(1.0, 2.2, distance))
        color = (246, 242, 176)
    elif name.startswith("mark_"):
        radius = np.sqrt((x / 90) ** 2 + (y / 45) ** 2)
        # A broad band with short fades on both the inner and outer edges.
        alpha = 0.92 * smoothstep(0.56, 0.68, radius) * (1 - smoothstep(0.90, 1.05, radius))
        color = (163, 53, 53) if name == "mark_fight" else (255, 255, 255)
    else:
        rx, ry, sigma, peak = {
            "select_char": (58, 29, 0.052, 0.83),
            "menu_select": (58, 59, 0.052, 0.83),
            "magic_select": (36.5, 37.5, 0.045, 0.91),
        }[name]
        radius = np.sqrt((x / rx) ** 2 + (y / ry) ** 2)
        distance = abs(radius - 1)
        # Narrow luminous core with a softer, low-opacity halo.
        alpha = peak * (0.84 * np.exp(-0.5 * (distance / sigma) ** 2)
                        + 0.16 * np.exp(-0.5 * (distance / (sigma * 1.9)) ** 2))
    alpha = alpha.reshape(height, SAMPLES, width, SAMPLES).mean(axis=(1, 3))
    pixels = np.empty((height, width, 4), dtype=np.uint8)
    pixels[..., :3] = color
    pixels[..., 3] = np.rint(alpha * 255).astype(np.uint8)
    pixels[pixels[..., 3] == 0] = 0
    return Image.fromarray(pixels)


if __name__ == "__main__":
    for name in SIZES:
        path = OUTPUT / f"{name}.png"
        render(name).save(path)
        print(path)
