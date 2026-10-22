#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Seeded wind vortex and shattering ice; requires Pillow and NumPy."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = {'wind': (7, (102,230), 10, 1.5), 'ice': (3, (119,142), 15, 1.5)}
SCALE = 3


def render(seed: int, variant: str) -> list[Image.Image]:
    _,size,count,_ = VARIANTS[variant]
    rng = np.random.default_rng(seed)
    particles = rng.random((330,7))
    frames=[]
    for i in range(count):
        t=i/(count-1)
        image=Image.new('RGBA',(size[0]*SCALE,size[1]*SCALE))
        draw=ImageDraw.Draw(image)
        def polygon(points,color):
            draw.polygon([(x*SCALE,y*SCALE) for x,y in points],fill=color)
        def line(points,color,width=1):
            draw.line([(x*SCALE,y*SCALE) for x,y in points],fill=color,width=max(1,round(width*SCALE)))
        if variant=='wind':
            envelope=np.sin(np.pi*t)**.65
            for ribbon in range(48):
                a,b,c,d,e,f,g=particles[ribbon]
                phase=a*6.28+t*12
                start=(b+t*.35)%0.8
                points=[]
                for u in np.linspace(start,min(1,start+.12+c*.28),55):
                    radius=(4+30*u**1.2)*(0.85+.15*np.sin(u*31+phase))
                    angle=phase+u*20
                    x=51+radius*np.cos(angle)+4*np.sin(u*5+t*3)
                    y=207-178*u+radius*.18*np.sin(angle)
                    points.append((x,y,angle))
                for a,b in zip(points,points[1:]):
                    front=(np.sin(a[2])+1)/2
                    alpha=int(envelope*(18+65*front))
                    color=(138+int(46*front),143+int(44*front),137+int(44*front),alpha)
                    line([a[:2],b[:2]],color,.45+.35*front)
            for a,b,c,d,e,f,g in particles[:160]:
                h=(a+t*.6)%1
                angle=b*6.28+t*12+h*15
                radius=(4+29*h)*(.7+.3*c)
                x=51+radius*np.cos(angle)
                y=207-178*h+radius*.18*np.sin(angle)
                r=.35+d*.6
                draw.ellipse(((x-r)*SCALE,(y-r)*SCALE,(x+r)*SCALE,(y+r)*SCALE),
                             fill=(188,186,169,int(155*envelope*(.4+.6*e))))
        else:
            shatter=np.clip((t-.32)/.68,0,1)
            solid=1-np.clip((t-.32)/.12,0,1)
            top=[(59,18),(91,33),(60,49),(28,34)]
            left=[(28,34),(60,49),(60,119),(28,103)]
            right=[(60,49),(91,33),(91,103),(60,119)]
            if solid>0:
                polygon(left,(94,154,179,int(225*solid)))
                polygon(right,(38,85,112,int(240*solid)))
                polygon(top,(167,217,231,int(235*solid)))
                for points in [top+[top[0]],left+[left[0]],right+[right[0]]]:
                    line(points,(203,240,248,int(200*solid)),.8)
                polygon([(29,65),(31,102),(58,116),(47,103)],(210,244,249,int(140*solid)))
                # Fine fracture lines stay attached until the block breaks apart.
                for points in [[(45,42),(49,63),(40,77),(46,97)],[(60,70),(74,63),(78,43)],
                               [(49,63),(60,70),(63,94),(76,106)],[(60,49),(64,35),(78,27)]]:
                    line(points,(218,249,255,int((65+120*t)*solid)),.45)
            for a,b,c,d,e,f,g in particles:
                face=(top,left,right)[min(int(a*3),2)]
                p0,p1,p3=np.array(face[0]),np.array(face[1]),np.array(face[3])
                p=p0+b*(p1-p0)+c*(p3-p0)
                angle=d*2*np.pi
                distance=shatter*(7+25*e)
                x=p[0]+np.cos(angle)*distance
                y=p[1]+np.sin(angle)*distance*.45+8*shatter**2
                radius=(.5+f*1.2)*(1-.5*shatter)
                rotation=angle+shatter*9
                alpha=int(230*(1-shatter)**1.2*(1-solid))
                if not alpha:
                    continue
                points=[(x+np.cos(rotation+k)*radius,y+np.sin(rotation+k)*radius*1.8)
                        for k in (0,2.1,4.2)]
                polygon(points,(120+int(120*g),177+int(70*g),209+int(46*g),alpha))
        # Keep a clear margin around the sprites for ordinary alpha compositing.
        image=image.resize(size,Image.Resampling.LANCZOS)
        frames.append(image)
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
