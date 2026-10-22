#!/usr/bin/env python3
# SPDX-License-Identifier: CC0-1.0
"""Extract a draw/release animation from johnnytal's CC0 bow sheet (Pillow, NumPy)."""
import argparse
from pathlib import Path
from PIL import Image
from render_fireball import previews

ROOT=Path(__file__).resolve().parent.parent
# Sheet: 6 columns × 4 rows of 70×90. Release cells run backwards.
SOURCE_FRAMES=(0,4,8,11,23,19,15,12)
SIZE=(90,56)
DURATION = 1.05


def extract(source: Path) -> list[Image.Image]:
    sheet=Image.open(source).convert('RGBA')
    if sheet.size!=(420,360):
        raise ValueError('Expected a 420×360 sheet of 70×90 cells')
    frames=[]
    for index in SOURCE_FRAMES:
        col,row=index%6,index//6
        cell=sheet.crop((col*70,row*90,(col+1)*70,(row+1)*90))
        cell=cell.resize((35,45),Image.Resampling.LANCZOS)
        frame=Image.new('RGBA',SIZE)
        # Fixed cell origin preserves the bow position throughout the draw/release.
        frame.paste(cell,(7,5))
        frames.append(frame)
    return frames


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'particles/sources/bow.png')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'client/textures/illarion/effects')
    parser.add_argument('--preview-dir',type=Path,default=ROOT/'particles/bow-preview')
    args=parser.parse_args();frames=extract(args.source)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for i,frame in enumerate(frames):frame.save(args.output_dir/f'bow-{i}.png')
    previews(frames,args.preview_dir,DURATION)
    print(f'Extracted {len(frames)} bow frames')


if __name__=='__main__':
    main()
