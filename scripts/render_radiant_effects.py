#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Seeded rising fire, warm starburst, and cyan beam; Pillow and NumPy."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = {'flamestrike': (36, (37, 170), 20, 1.8),
            'glowing': (31, (117, 114), 16, 1.95),
            'light': (37, (63, 252), 21, 2.25)}
SCALE = 3


def render(seed: int, variant: str) -> list[Image.Image]:
    _, size, count, _ = VARIANTS[variant]
    rng = np.random.default_rng(seed)
    waves = rng.random((18, 3))
    rays = rng.random((32, 3))
    particles = rng.random((160, 4))
    y, x = np.mgrid[:size[1]*SCALE, :size[0]*SCALE] / SCALE
    frames = []
    for index in range(count):
        t = index / (count - 1)
        envelope = np.sin(np.pi*t)**0.8
        noise = sum(np.sin(x*(.3+a)*np.cos(b*6.28) + y*(.2+a*.5)*np.sin(b*6.28)
                           + c*6.28 + t*9) for a,b,c in waves)/9
        if variant == 'flamestrike':
            center = 143 - 111*t
            h = (center + 12 - y)/47
            width = 7*np.clip(1-h,0,1)**.7 + .4
            sway = np.sin(h*12-t*8)*np.clip(h,0,1)*2
            profile = 1-((x-18-sway)/width)**2 - h*.45 + noise*.35
            density = np.clip(profile,0,1)*np.clip(h*6,0,1)*np.clip((1-h)*6,0,1)
            alpha = np.clip(density*3,0,1)*envelope
            heat = np.clip(density*(1-np.clip(h,0,1)*.4),0,1)
            palette = np.array([[112,17,3],[215,48,3],[255,128,7],[255,220,55],[255,249,176]])
        elif variant == 'glowing':
            dx,dy = x-58,y-57
            radius = np.hypot(dx,dy)
            theta = np.arctan2(dy,dx)
            expansion = 0.25 + .75*envelope
            core = np.exp(-(radius/(7.5*expansion))**2)
            halo = np.exp(-(radius/(18*expansion))**2)*.28
            streaks = np.zeros_like(x)
            for a,b,c in rays:
                angle = a*2*np.pi + .025*np.sin(t*7+c*6.28)
                delta = np.arctan2(np.sin(theta-angle),np.cos(theta-angle))
                streaks += np.exp(-(delta/(.012+.025*b))**2)*np.exp(-radius/(expansion*(9+12*c)))
            alpha = np.clip(core*2 + halo + streaks*.9,0,1)*envelope
            heat = np.clip(core*2 + streaks*.6,0,1)
            palette = np.array([[207,119,95],[245,182,151],[255,227,204],[255,251,238],[255,255,255]])
        else:
            # A finite column travels upward, with soft caps and internal motes.
            bottom = 235-133*t
            top = bottom-170
            cap = np.clip((y-top)/12,0,1)*np.clip((bottom-y)/12,0,1)
            horizontal = np.exp(-((x-31)/6)**2)
            density = horizontal*cap*np.clip(.65+noise*.35,0,1)
            motes = np.zeros_like(x)
            for a,b,c,d in particles:
                px = 31+(a-.5)*14
                py = top + ((b-t*(.25+c*.2))%1)*170
                motes += np.exp(-((x-px)/(.4+d*.5))**2-((y-py)/1.1)**2)*cap
            alpha = np.clip(density*.55 + motes*.55,0,1)*envelope
            heat = np.clip(density*.65+motes*.4,0,1)
            palette = np.array([[14,81,88],[29,139,148],[63,194,194],[134,237,228],[215,255,247]])
        rgb = np.stack([np.interp(heat,np.linspace(0,1,len(palette)),palette[:,c]) for c in range(3)],-1)
        edge = np.clip(np.minimum.reduce([x-3,y-3,size[0]-4-x,size[1]-4-y])/4,0,1)
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
