#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Seeded purple flame, golden beam, and cyan sparkles; Pillow and NumPy."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from render_fireball import previews

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = {'violett': (51, (115, 224), 13, 1.5),
            'sun': (46, (50, 400), 8, 1.5),
            'sprinkle': (52, (117, 125), 24, 2.7)}
SCALE = 3


def render(seed: int, variant: str) -> list[Image.Image]:
    _, size, count, _ = VARIANTS[variant]
    rng = np.random.default_rng(seed)
    waves = rng.random((18,3))
    particles = rng.random((150,6))
    y,x = np.mgrid[:size[1]*SCALE,:size[0]*SCALE]/SCALE
    frames = []
    for i in range(count):
        t = i/(count if variant=='violett' else count-1)
        pulse = np.sin(np.pi*t)**.8
        if variant=='sprinkle':
            image = Image.new('RGBA',(size[0]*SCALE,size[1]*SCALE))
            draw = ImageDraw.Draw(image)
            for a,b,c,d,e,f in particles:
                twinkle = (.5+.5*np.sin(d*2*np.pi+t*24))**3
                if twinkle<.08 or b>pulse:
                    continue
                angle = a*2*np.pi+t*5
                radius = (8+30*np.sqrt(b))*(.6+.4*pulse)
                px = (58+np.cos(angle)*radius)*SCALE
                py = (58+np.sin(angle)*radius*.65 + 5*np.sin(t*5+c*6.28))*SCALE
                r = (.9+e*1.3)*SCALE*(.5+twinkle)
                color = (100+int(110*f),226+int(29*f),255,int(255*pulse*(.5+.5*twinkle)))
                draw.polygon([(px-r*2,py),(px-r*.2,py-r*.2),(px,py-r*2),
                              (px+r*.2,py-r*.2),(px+r*2,py),(px+r*.2,py+r*.2),
                              (px,py+r*2),(px-r*.2,py+r*.2)],fill=color)
            glow=image.filter(ImageFilter.GaussianBlur(SCALE))
            glow.putalpha(glow.getchannel('A').point(lambda a:int(a*.35)))
            image=Image.alpha_composite(glow,image)
        else:
            if variant=='violett':
                noise=sum(np.sin(x*(.15+a*.35)*np.cos(b*6.28)+y*(.12+a*.25)*np.sin(b*6.28)
                                 +c*6.28+t*2*np.pi*(1+int(a*3))) for a,b,c in waves)/9
                h=np.clip((191-y)/164,0,1)
                sway=(4*np.sin(h*9-t*2*np.pi)+2*np.sin(h*19+t*4*np.pi))*h
                width=26*(1-h)**.8+1
                density=np.clip(1-((x-57-sway)/width)**2-h*.65+noise*.5,0,1)
                density*=np.clip((y-23)/16,0,1)*np.clip((198-y)/15,0,1)
                base=np.exp(-((x-57)/24)**2-((y-186)/9)**2)
                ring_radius=np.sqrt(((x-57)/25)**2+((y-186)/10)**2)
                ring=np.exp(-((ring_radius-1)/.13)**2)
                alpha=np.clip(density*1.3+base*.6+ring*.45,0,1)
                heat=np.clip(density*.6+base*.6+ring*.2,0,1)
                palette=np.array([[65,12,78],[135,29,149],[202,57,200],[244,121,229],[255,202,250]])
            else:
                # Downward rays land on a small flattened ground glow.
                beam=np.exp(-((x-25)/(1.2+2.3*(1-y/400)))**2)
                beam*=np.clip((y-5)/10,0,1)*np.clip((377-y)/34,0,1)
                shimmer=.85+.15*np.sin(y*.09-t*8)
                halo=np.exp(-((x-25)/7)**2)*.1*np.clip((380-y)/35,0,1)
                ground=np.exp(-((x-25)/8)**2-((y-379)/3.2)**2)
                alpha=np.clip(beam*shimmer+halo+ground*.9,0,1)*pulse
                heat=np.clip(beam*.8+ground*.9,0,1)
                palette=np.array([[116,106,43],[191,182,91],[235,228,153],[255,252,210],[255,255,240]])
            rgb=np.stack([np.interp(heat,np.linspace(0,1,len(palette)),palette[:,c]) for c in range(3)],-1)
            edge=np.clip(np.minimum.reduce([x-3,y-3,size[0]-4-x,size[1]-4-y])/4,0,1)
            alpha*=edge*edge*(3-2*edge)
            rgba=np.dstack([rgb,alpha*255]).astype('uint8');rgba[rgba[:,:,3]==0]=0
            image=Image.fromarray(rgba)
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
