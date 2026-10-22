#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Seeded explosion, looping flame, and falling red particles; Pillow and NumPy."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = {'explo': (44, (83, 77), 20, 0.9),
            'fire_field': (38, (38, 120), 5, 0.45),
            'fall': (32, (138, 283), 13, 1.5)}
SCALE = 3


def render(seed: int, variant: str) -> list[Image.Image]:
    _, size, count, _ = VARIANTS[variant]
    rng = np.random.default_rng(seed)
    particles = rng.random((100 if variant == 'explo' else 20, 6))
    waves = rng.random((16, 3))
    y, x = np.mgrid[:size[1]*SCALE, :size[0]*SCALE] / SCALE
    frames = []
    for index in range(count):
        t = index / (count if variant == 'fire_field' else count - 1)
        density = np.zeros_like(x)
        noise = sum(np.sin(x * (0.3 + a) * np.cos(b*6.28)
                           + y * (0.2 + a*.5) * np.sin(b*6.28)
                           + c*6.28 + t*2*np.pi*(1 + int(a*3)))
                    for a, b, c in waves) / 8
        if variant == 'fire_field':
            # Integer temporal frequencies make the continuous field exactly periodic.
            h = np.clip((108 - y) / 95, 0, 1)
            sway = (1.5*np.sin(h*10 - t*2*np.pi) + np.sin(h*23+t*4*np.pi))*h
            width = 10.5 * (1-h)**0.65 + 0.5
            profile = 1 - ((x - 19 - sway) / width)**2 - h*.55
            density = np.clip(profile + noise*.32, 0, 1)
            density *= np.clip((110-y)/9, 0, 1) * np.clip((y-9)/10, 0, 1)
            base = np.exp(-((x-19)/9)**2 - ((y-94)/12)**2)
            density = np.maximum(density, base*.95)
            alpha = np.clip(density*3, 0, 1)
            heat = np.clip(density * (1-h*.5), 0, 1)
        elif variant == 'explo':
            envelope = np.sin(np.pi*t)**0.7
            for a,b,c,phase,r,speed in particles:
                angle = a*2*np.pi
                px = 41 + np.cos(angle)*(3+25*t)*np.sqrt(b)
                py = 53 + np.sin(angle)*(2+10*t)*np.sqrt(b) - (9+18*speed)*t
                radius = (1.1+2.5*r)*(0.5+np.sin(np.pi*t))
                density += np.exp(-(((x-px)/radius)**2 + ((y-py)/(radius*1.8))**2)*1.8)
            density *= np.clip(.8+noise*.9, 0, 1.5)
            alpha = (1-np.exp(-density*1.4))*envelope
            heat = (1-np.exp(-density*.65))*(1-.45*t)
        else:
            # Persistent droplets fall together, with a slight initial upward kick.
            for a,b,c,phase,r,speed in particles:
                px = 69 + (a-.5)*(37+12*t) + np.sin(phase*6.28+t*3)*3
                py = 42 + (b-.5)*34 - 32*t + (193+15*speed)*t*t
                radius = 2.2 + r*3.4
                density += np.exp(-(((x-px)/radius)**2 + ((y-py)/(radius*1.25))**2)*1.6)
            alpha = (1-np.exp(-density*1.8))*(.65+.35*np.sin(np.pi*t))
            heat = np.clip(1-np.exp(-density*.9), 0, 1)
        if variant == 'fall':
            palette = np.array([[83,15,20],[147,35,40],[197,66,68],[245,144,136]])
        else:
            palette = np.array([[105,13,3],[209,42,3],[255,110,5],[255,207,44],[255,249,166]])
        rgb = np.stack([np.interp(heat, np.linspace(0,1,len(palette)),palette[:,c]) for c in range(3)],-1)
        # Dissipate wisps before the canvas boundaries.
        edge = np.clip(np.minimum.reduce([x-3, y-3, size[0]-4-x, size[1]-4-y])/3,0,1)
        alpha *= edge*edge*(3-2*edge)
        rgba = np.dstack([rgb,alpha*255]).astype('uint8')
        rgba[rgba[:,:,3]==0] = 0
        frames.append(Image.fromarray(rgba).resize(size,Image.Resampling.LANCZOS))
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=VARIANTS,required=True)
    parser.add_argument('--seed',type=int,default=90210)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'client/textures/illarion/effects')
    parser.add_argument('--preview-dir',type=Path)
    args = parser.parse_args()
    frames = render(args.seed,args.variant)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for i,frame in enumerate(frames):
        frame.save(args.output_dir/f'{args.variant}-{i}.png')
    previews(frames,args.preview_dir or ROOT/'particles'/f'{args.variant}-preview',VARIANTS[args.variant][3])
    print(f'Rendered {len(frames)} {args.variant} frames')


if __name__ == '__main__':
    main()
