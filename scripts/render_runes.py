"""Render rune SVGs to transparent PNGs.

Run with: python3 scripts/render_runes.py
Requires ksvgtopng (KDE SVG tools) and the Noto fonts used by the sources.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def positive_int(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("dimension must be positive")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "runes")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "client/textures/illarion/ui"
    )
    parser.add_argument(
        "--width", type=positive_int, default=86,
        help="PNG width in pixels (default: 86)",
    )
    parser.add_argument(
        "--height", type=positive_int, default=86,
        help="PNG height in pixels (default: 86)",
    )
    parser.add_argument("--renderer", default="ksvgtopng", help="path to ksvgtopng")
    args = parser.parse_args()

    sources = sorted(args.source.resolve().glob("*.svg"))
    if not sources:
        parser.error(f"no SVG files found in {args.source}")
    renderer = shutil.which(args.renderer)
    if renderer is None:
        parser.error(f"renderer not found: {args.renderer}; install KDE SVG tools")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Qt's offscreen backend also works on machines without a desktop session.
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    for source in sources:
        target = output / f"{source.stem}.png"
        try:
            subprocess.run(
                [renderer, str(args.width), str(args.height), str(source), str(target)],
                check=True, env=env,
            )
        except subprocess.CalledProcessError as exc:
            parser.exit(1, f"Failed to render {source}: {exc}\n")
        print(target)
    print(f"Rendered {len(sources)} runes to {output}")


if __name__ == "__main__":
    main()
