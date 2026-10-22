#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Seeded water ripples and branching lightning; Pillow and NumPy."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = {'platsch': (11, (49,25), 5, 1.2), 'blitz': (2, (200,300), 6, 0.75)}
SCALE = 4


def render(seed: int, variant: str) -> list[Image.Image]:
    _,size,count,_ = VARIANTS[variant]
    rng=np.random.default_rng(seed)
    # Persistent path parameters keep branches coherent over time.
    offsets=rng.uniform(-16,16,16)
    branches=rng.random((9,4))
    phase=rng.uniform(0,2*np.pi)
    frames=[]
    for i in range(count):
        t=i/(count-1)
        image=Image.new('RGBA',(size[0]*SCALE,size[1]*SCALE))
        draw=ImageDraw.Draw(image)
        if variant=='platsch':
            for delay in (0,.23,.46):
                age=t-delay
                if age<0:
                    continue
                radius=5+15*age
                opacity=int(230*(1-.62*age))
                # Separate light and dark edges give the water wave a raised rim.
                box=((24-radius)*SCALE,(12-radius*.4)*SCALE,
                     (24+radius)*SCALE,(12+radius*.4)*SCALE)
                draw.ellipse(box,outline=(35,108,216,opacity),width=2)
                draw.arc((box[0],box[1]-2,box[2],box[3]-2),185,350,
                         fill=(168,225,255,opacity),width=2)
                draw.arc((box[0],box[1]+2,box[2],box[3]+2),5,165,
                         fill=(17,53,129,int(opacity*.7)),width=2)
        else:
            intensity=(.9,1,.95,1,.8,.45)[i]
            points=[]
            for j,offset in enumerate(offsets):
                y=13+j*17
                x=92+offset+13*np.sin(j*.6+phase)+4*np.sin(t*11+j*2)
                points.append((x,y))
            paths=[(points,1.4)]
            for k,(a,b,c,d) in enumerate(branches):
                start=3+int(a*9)
                if i==5 and k>3:
                    continue
                origin=np.array(points[start])
                direction=1 if b>.4 else -1
                length=22+43*c
                path=[tuple(origin)]
                for step in range(1,6):
                    fraction=step/5
                    px=origin[0]+direction*length*fraction
                    py=origin[1]+(d-.5)*40*fraction+6*np.sin(step*2+k+t*9)
                    path.append((px,py))
                paths.append((path,.65))
            blue=Image.new('RGBA',image.size)
            bd=ImageDraw.Draw(blue)
            for path,width in paths:
                coords=[(x*SCALE,y*SCALE) for x,y in path]
                bd.line(coords,fill=(62,130,255,int(200*intensity)),width=round((width+2)*SCALE),joint='curve')
            glow=blue.filter(ImageFilter.GaussianBlur(3*SCALE))
            image=Image.alpha_composite(glow,blue.filter(ImageFilter.GaussianBlur(.65*SCALE)))
            draw=ImageDraw.Draw(image)
            for path,width in paths:
                coords=[(x*SCALE,y*SCALE) for x,y in path]
                draw.line(coords,fill=(210,238,255,int(255*intensity)),width=max(1,round(width*SCALE)),joint='curve')
        frames.append(image.resize(size,Image.Resampling.LANCZOS))
    return frames


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=VARIANTS,required=True)
    parser.add_argument('--seed',type=int,default=90210)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'client/textures/illarion/effects')
    parser.add_argument('--preview-dir',type=Path)
    args=parser.parse_args();frames=render(args.seed,args.variant)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for i,frame in enumerate(frames):frame.save(args.output_dir/f'{args.variant}-{i}.png')
    previews(frames,args.preview_dir or ROOT/'particles'/f'{args.variant}-preview',VARIANTS[args.variant][3])
    print(f'Rendered {len(frames)} {args.variant} frames')


if __name__=='__main__':
    main()
