#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Seeded orbiting embers and smoke traces; requires Pillow and NumPy."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from render_fireball import previews

ROOT=Path(__file__).resolve().parent.parent
SIZE=(144,197)
FRAMES=19
DURATION = 1.5
SCALE=3


def render(seed: int) -> list[Image.Image]:
    rng=np.random.default_rng(seed)
    particles=rng.random((80,5))
    traces=rng.random((18,6))
    y,x=np.mgrid[:SIZE[1]*SCALE,:SIZE[0]*SCALE]/SCALE
    frames=[]
    for i in range(FRAMES):
        t=i/(FRAMES-1)
        envelope=np.sin(np.pi*t)**.65
        density=np.zeros_like(x)
        hot=np.zeros_like(x)
        for a,b,c,d,e in particles:
            lag=a*1.8
            angle=t*4*np.pi-lag
            px=72+np.cos(angle)*(33+(b-.5)*7)
            py=88+np.sin(angle)*17+(c-.5)*5
            radius=1.1+d*2
            kernel=np.exp(-(((x-px)/radius)**2+((y-py)/(radius*.9))**2)*1.4)
            density+=kernel*(1-a*.8)
            hot+=kernel*(1-a)*(.4+.6*e)
        heat=np.clip(1-np.exp(-hot*.75),0,1)
        alpha=(1-np.exp(-density*1.5))*envelope
        palette=np.array([[83,31,14],[149,53,13],[220,91,17],[255,166,49],[255,226,134]])
        rgb=np.stack([np.interp(heat,np.linspace(0,1,len(palette)),palette[:,c]) for c in range(3)],-1)
        rgba=np.dstack([rgb,alpha*255]).astype('uint8');rgba[rgba[:,:,3]==0]=0
        embers=Image.fromarray(rgba)
        smoke=Image.new('RGBA',embers.size)
        draw=ImageDraw.Draw(smoke)
        for a,b,c,d,e,f in traces:
            angle=a*2*np.pi+t*4*np.pi
            px=72+np.cos(angle)*(29+b*12)
            py=88+np.sin(angle)*18
            points=[(px,py)]
            for step in range(1,5):
                u=step/4
                points.append((px+(c-.5)*44*u+np.sin(step*2+angle)*11*u,
                               py-(14+58*d)*u+np.sin(step*3+e*6.28+t*7)*9*u))
            draw.line([(np.clip(px,8,SIZE[0]-9)*SCALE,
                        np.clip(py,8,SIZE[1]-9)*SCALE) for px,py in points],
                      fill=(78,72,61,int(envelope*(24+45*f))),width=2)
        image=Image.alpha_composite(smoke,embers).resize(SIZE,Image.Resampling.LANCZOS)
        frames.append(image)
    return frames


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=90210)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'client/textures/illarion/effects')
    parser.add_argument('--preview-dir',type=Path,default=ROOT/'particles/spell-preview')
    args=parser.parse_args();frames=render(args.seed)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for i,frame in enumerate(frames):frame.save(args.output_dir/f'spell-{i}.png')
    previews(frames,args.preview_dir,DURATION)
    print(f'Rendered {len(frames)} spell frames')


if __name__=='__main__':
    main()
