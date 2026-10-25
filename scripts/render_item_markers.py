#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Generate the blocked and unknown-item markers using Pillow, without inputs."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "client/textures/illarion/items/markers"


def blocked() -> Image.Image:
    """Red prohibition sign on the existing 37×38 transparent canvas."""
    image = Image.new("RGBA", (37, 38))
    draw = ImageDraw.Draw(image)
    red = (255, 0, 0, 255)
    draw.ellipse((0, 0, 36, 37), outline=red, width=5)
    draw.line((6, 30, 30, 6), fill=red, width=5)
    return image


def unknown_item() -> Image.Image:
    """Pixel question mark centered on the existing 128×64 tile canvas."""
    image = Image.new("RGBA", (128, 64))
    draw = ImageDraw.Draw(image)
    white = (255, 255, 255, 255)
    # Explicit geometry avoids dependence on installed fonts or input images.
    draw.line(
        [(58, 27), (58, 24), (62, 20), (69, 20), (74, 25),
         (74, 30), (66, 36), (66, 39)],
        fill=white,
        width=3,
    )
    draw.rectangle((65, 42, 67, 44), fill=white)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, render in (("blocked.png", blocked),
                             ("unknownItem.png", unknown_item)):
        path = args.output_dir / filename
        render().save(path)
        print(path)


if __name__ == "__main__":
    main()
