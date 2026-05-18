#!/usr/bin/env python3

from __future__ import annotations

import argparse
import colorsys
import math
from array import array
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a looping animated water texture as individual PNG frames."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tiles" / "water",
        help="Directory to write PNG frames into.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=256,
        help="Width and height of each square frame in pixels.",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=16,
        help="Number of frames in the loop.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Seed used for the procedural pattern.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing PNG frames in the output directory before rendering.",
    )
    args = parser.parse_args()
    if args.size <= 0:
        raise SystemExit("--size must be positive")
    if args.frames <= 0:
        raise SystemExit("--frames must be positive")
    return args


def fract(value: float) -> float:
    return value - math.floor(value)


def smoothstep01(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def hash_2d(ix: int, iy: int, seed: int) -> float:
    value = (
        ix * 374761393
        + iy * 668265263
        + seed * 1442695040888963407
    ) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 33
    value = (value * 1274126177) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 29
    value = (value * 14313749767032793493) & 0xFFFFFFFFFFFFFFFF
    value ^= value >> 32
    return (value & 0xFFFFFFFF) / 0xFFFFFFFF


def tileable_value_noise(u: float, v: float, cells: int, seed: int) -> float:
    x = u * cells
    y = v * cells
    x0 = math.floor(x)
    y0 = math.floor(y)
    tx = smoothstep01(x - x0)
    ty = smoothstep01(y - y0)

    x1 = x0 + 1
    y1 = y0 + 1

    def sample(ix: int, iy: int) -> float:
        return hash_2d(ix % cells, iy % cells, seed)

    n00 = sample(x0, y0)
    n10 = sample(x1, y0)
    n01 = sample(x0, y1)
    n11 = sample(x1, y1)
    return lerp(lerp(n00, n10, tx), lerp(n01, n11, tx), ty)


def fbm(u: float, v: float, time_phase: float, seed: int) -> float:
    total = 0.0
    amplitude = 0.5
    amplitude_sum = 0.0
    for octave, cells in enumerate((3, 6, 12, 24), start=1):
        drift_u = fract(u + math.cos(time_phase * math.tau + octave * 0.7) * (0.12 / cells))
        drift_v = fract(v + math.sin(time_phase * math.tau + octave * 1.1) * (0.12 / cells))
        total += tileable_value_noise(drift_u, drift_v, cells, seed + octave * 97) * amplitude
        amplitude_sum += amplitude
        amplitude *= 0.5
    return total / amplitude_sum


def sample_height(u: float, v: float, time_phase: float, seed: int) -> float:
    angle = time_phase * math.tau
    flow_u = fract(u + 0.018 * math.cos(angle * 0.6))
    flow_v = fract(v + time_phase * 0.12)

    bend = (tileable_value_noise(fract(flow_u * 1.1), fract(flow_v * 0.9), 6, seed + 101) - 0.5) * 0.20
    shear = (tileable_value_noise(fract(flow_u * 0.8), fract(flow_v * 1.3), 4, seed + 202) - 0.5) * 0.10
    micro = (tileable_value_noise(fract(flow_u * 2.0), fract(flow_v * 2.4), 12, seed + 303) - 0.5) * 0.05

    phase = flow_v + bend + shear + micro
    ridge_a = math.sin(phase * math.tau * 4.0 - angle * 1.0 + flow_u * math.tau * 0.35)
    ridge_b = math.sin(phase * math.tau * 6.9 - angle * 1.6 - flow_u * math.tau * 0.22)
    ridge_c = math.sin(phase * math.tau * 9.5 - angle * 2.0 + flow_u * math.tau * 0.14)

    envelope = tileable_value_noise(fract(flow_u * 0.9), fract(flow_v * 0.7), 5, seed + 404) - 0.5
    crest_mask = smoothstep01((ridge_a * 0.6 + envelope * 0.8 + 0.2) / 0.9)

    height = (
        ridge_a * 0.17
        + ridge_b * 0.07
        + ridge_c * 0.03
        + envelope * 0.12
        + crest_mask * 0.05
    )
    return height


def water_color(height: float, gradient_x: float, gradient_y: float) -> tuple[int, int, int, int]:
    light_x = -0.6
    light_y = -0.8
    light_z = 0.9

    nx = -gradient_x * 2.2
    ny = -gradient_y * 2.2
    nz = 1.0
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= length
    ny /= length
    nz /= length

    diffuse = max(0.0, nx * light_x + ny * light_y + nz * light_z)
    fresnel = pow(max(0.0, 1.0 - nz), 1.9)
    sheen = pow(max(0.0, diffuse), 5.0)

    depth = smoothstep01((height + 0.38) / 0.76)
    trough = smoothstep01((-height + 0.18) / 0.45)

    hue = lerp(0.555, 0.575, depth)
    saturation = lerp(0.54, 0.42, depth)
    value = 0.29 + diffuse * 0.13 + fresnel * 0.07 + sheen * 0.05 - trough * 0.04
    value = max(0.0, min(1.0, value))

    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    red = min(1.0, red + sheen * 0.015)
    green = min(1.0, green + sheen * 0.03)
    blue = min(1.0, blue + sheen * 0.04)

    return (
        int(red * 255.0),
        int(green * 255.0),
        int(blue * 255.0),
        255,
    )


def render_frame(size: int, frame_index: int, frame_count: int, seed: int) -> Image.Image:
    image = Image.new("RGBA", (size, size))
    pixels = image.load()
    inv_size = 1.0 / size
    time_phase = frame_index / frame_count

    heights = array("f", [0.0]) * (size * size)
    for y in range(size):
        v = y * inv_size
        for x in range(size):
            u = x * inv_size
            heights[y * size + x] = sample_height(u, v, time_phase, seed)

    for y in range(size):
        up = (y - 1) % size
        down = (y + 1) % size
        row_index = y * size
        up_index = up * size
        down_index = down * size
        for x in range(size):
            left = (x - 1) % size
            right = (x + 1) % size
            center_index = row_index + x
            gradient_x = heights[row_index + right] - heights[row_index + left]
            gradient_y = heights[down_index + x] - heights[up_index + x]
            pixels[x, y] = water_color(heights[center_index], gradient_x, gradient_y)

    return image


def render_frames(output_dir: Path, size: int, frame_count: int, seed: int, clean: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for existing in output_dir.glob("*.png"):
            existing.unlink()

    for frame_index in range(frame_count):
        image = render_frame(size, frame_index, frame_count, seed)
        image.save(output_dir / f"frame_{frame_index:04d}.png")


def main() -> None:
    args = parse_args()
    render_frames(args.output_dir.resolve(), args.size, args.frames, args.seed, args.clean)


if __name__ == "__main__":
    main()
