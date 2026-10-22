#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Animate supplied CC0 combat icons; requires Pillow and NumPy for previews."""
import argparse
import json
import math
from pathlib import Path
from PIL import Image
from render_fireball import previews

ROOT=Path(__file__).resolve().parent.parent
SCALE=4
# Game visual, canvas, normalized icon size, initial rotation.
ANIMATIONS={
    'sword':(17,(77,55),(12,40),45),
    'mace':(19,(79,64),(14,42),45),
    'dagger':(20,(55,13),(30,8),-45),
    'shield':(18,(34,56),(19,27),0),
    'claw':(21,(27,44),(16,26),0),
    'boxing':(22,(58,54),(16,19),0),
}


def load_icon(source: Path, name: str) -> Image.Image:
    _,_,target,angle=ANIMATIONS[name]
    icon=Image.open(source/f'{name}.png').convert('RGBA')
    icon=icon.crop(icon.getchannel('A').getbbox())
    icon=icon.resize((icon.width*SCALE,icon.height*SCALE),Image.Resampling.NEAREST)
    if angle:
        icon=icon.rotate(angle,Image.Resampling.BICUBIC,expand=True)
        icon=icon.crop(icon.getchannel('A').getbbox())
    icon.thumbnail((target[0]*SCALE,target[1]*SCALE),Image.Resampling.LANCZOS)
    return icon


def pose(name: str,t: float):
    ease=t*t*(3-2*t)
    if name=='sword':return (16,46,-95*ease,1)
    if name=='mace':return (18,49,-85*ease,1)
    if name=='dagger':return (18+17*math.sin(math.pi*t),6.5,0,1)
    if name=='boxing':return (12+32*ease,39-20*ease,12*math.sin(math.pi*t),1)
    if name=='claw':return (13.5,17+10*ease,-12*math.sin(math.pi*t),1)
    return (17,34-5*ease,-32*ease,1-.28*ease)


def render(name: str,source: Path) -> tuple[list[Image.Image],dict]:
    gfx,size,_,_=ANIMATIONS[name]
    visual=json.loads((ROOT/f'client/data/illarion/visuals/gfx/gfx_{gfx}.json').read_text())
    icon=load_icon(source,name)
    frames=[]
    for i in range(len(visual['textures'])):
        t=i/(len(visual['textures'])-1)
        px,py,angle,squash=pose(name,t)
        sprite=icon
        if squash!=1:sprite=sprite.resize((round(sprite.width*squash),sprite.height),Image.Resampling.BICUBIC)
        layer=Image.new('RGBA',(size[0]*SCALE,size[1]*SCALE))
        if name in ('sword','mace'):
            # Keep the grip anchored as the blade/head sweeps clockwise.
            anchor=(px*SCALE,py*SCALE)
            layer.paste(sprite,(round(anchor[0]-sprite.width/2),round(anchor[1]-sprite.height)))
            layer=layer.rotate(angle,Image.Resampling.BICUBIC,center=anchor)
        else:
            sprite=sprite.rotate(angle,Image.Resampling.BICUBIC,expand=True)
            layer.paste(sprite,(round(px*SCALE-sprite.width/2),round(py*SCALE-sprite.height/2)))
        frame=layer.resize(size,Image.Resampling.LANCZOS)
        # Remove negligible resampling fringes on the very short dagger canvas.
        alpha=frame.getchannel("A").point(lambda a: 0 if a<=2 else a)
        frame.putalpha(alpha)
        frames.append(frame)
    return frames,visual


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--animation',choices=ANIMATIONS)
    parser.add_argument('--source-dir',type=Path,default=ROOT/'particles/sources')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'client/textures/illarion/effects')
    parser.add_argument('--preview-dir',type=Path,help='Parent folder for <animation>-preview directories')
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    for name in ([args.animation] if args.animation else ANIMATIONS):
        frames,visual=render(name,args.source_dir)
        for i,frame in enumerate(frames):frame.save(args.output_dir/f'{name}-{i}.png')
        previews(frames,(args.preview_dir or ROOT/'particles')/f'{name}-preview',visual['duration'])
        print(f'{name}: rendered {len(frames)} frames')


if __name__=='__main__':
    main()
