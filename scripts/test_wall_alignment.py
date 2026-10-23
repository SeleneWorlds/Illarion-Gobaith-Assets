"""Regression tests for wall rasterization; run with python3 -m unittest discover -s scripts -p 'test_*.py'."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from sprite_pipeline import apply_alpha_mask_to_textures, crop_rendered_textures_to_alpha

ROOT = Path(__file__).resolve().parent.parent


def wall(item):
    visual = json.loads((ROOT / f'client/data/illarion/visuals/items/item_{item}.json').read_text())
    return Image.open(ROOT / visual['texture']).convert('RGBA'), visual


def assembly():
    canvas = Image.new('RGBA', (640, 512))
    # Screen projections of tile coordinates: (64*(x+y), 32*(x-y)).
    placements = [(240, 0, 0), (38, 0, 1), (38, 0, 2),
                  (33, -1, 0), (922, -2, 0), (33, -3, 0)]
    for item, x, y in placements:
        sprite, visual = wall(item)
        px = 320 + 64 * (x + y) + visual['offsetX'] - sprite.width // 2
        py = 320 + 32 * (x - y) - visual['offsetY'] - sprite.height
        canvas.alpha_composite(sprite, (px, py))
    return canvas


class WallAlignmentTests(unittest.TestCase):
    def test_all_grid_wall_outputs_have_integral_anchors(self):
        textures = set()
        for config in (ROOT / 'models/walls').rglob('*.json'):
            raw = json.loads(config.read_text())
            if not raw.get('gridAligned'):
                continue
            self.assertNotIn('alphaMask', raw, str(config))
            self.assertNotIn('offsetX', raw, str(config))
            self.assertNotIn('offsetY', raw, str(config))
            visual = json.loads((ROOT / 'client/data/illarion/visuals' / (raw['visual'] + '.json')).read_text())
            texture = ROOT / visual['texture']
            if texture in textures:
                continue
            textures.add(texture)
            with self.subTest(texture=str(texture)), Image.open(texture) as sprite:
                self.assertEqual(sprite.width % 2, 0)
                self.assertEqual(set(sprite.getchannel('A').getdata()), {0, 255})
                self.assertIsInstance(visual['offsetX'], int)
                self.assertIsInstance(visual['offsetY'], int)

    def test_four_example_items_have_integer_pixel_anchors(self):
        for item in (240, 38, 33, 922):
            with self.subTest(item=item):
                sprite, visual = wall(item)
                self.assertEqual(sprite.width % 2, 0)
                self.assertEqual(set(sprite.getchannel('A').getdata()), {0, 255})
                self.assertEqual(visual['offsetY'], -32)
                self.assertEqual(visual['offsetX'], {240: 0, 38: 24, 33: -24, 922: -24}[item])

    def test_join_columns_have_no_transparent_seams(self):
        alpha = assembly().getchannel('A')
        # Each join is a vertical segment on the visible wall face. Check both
        # sides, excluding only the top and ground silhouette boundaries.
        for sx, base_y in ((64, 0), (128, -32), (-64, 0), (-128, -32), (-192, -64)):
            for dx in (-1, 0, 1):
                for dy in range(-190, -3):
                    with self.subTest(join=(sx, base_y), dx=dx, dy=dy):
                        self.assertEqual(alpha.getpixel((320 + sx + dx, 320 + base_y + dy)), 255)

    def test_door_pairs_stay_on_the_correct_tile_edge(self):
        # Open/closed pairs from the door definitions; offsets must match
        # the expected edge as well as each other.
        for opened, closed, expected in (
            (86, 497, (24, -32)),
            (87, 922, (-24, -32)),
            (927, 925, (-24, -8)),
            (317, 926, (24, -8)),
        ):
            with self.subTest(pair=(opened, closed)):
                for item in (opened, closed):
                    sprite, visual = wall(item)
                    self.assertEqual((visual['offsetX'], visual['offsetY']), expected)
                    self.assertEqual(sprite.size, (80, 230))

    def test_north_window_and_south_pillar_use_the_correct_edge(self):
        for item, expected in ((318, (-24, -8)), (262, (0, -32))):
            with self.subTest(item=item):
                _, visual = wall(item)
                self.assertEqual((visual['offsetX'], visual['offsetY']), expected)
        # The pillar must meet both front faces of the southwest corner at
        # ground level, whose frontmost point is 32 pixels below tile origin.
        pillar, visual = wall(262)
        self.assertEqual(-visual['offsetY'], 32)
        self.assertEqual(pillar.width, 32)

    def test_open_doors_retain_their_cutouts(self):
        for item in (86, 87, 317, 927, 928):
            with self.subTest(item=item):
                sprite, _ = wall(item)
                alpha = sprite.getchannel('A')
                # The doorway must be open through its center, with a solid lintel
                # above and jambs on either side. This fails if the Boolean operand
                # stays behind when the wall rotates to a different direction.
                cx = sprite.width // 2
                cy = sprite.height // 2
                self.assertEqual(alpha.getpixel((cx, cy)), 0)
                self.assertEqual(alpha.getpixel((cx, cy - 50)), 0)
                self.assertEqual(alpha.getpixel((cx, cy + 60)), 0)
                self.assertEqual(alpha.getpixel((cx, 20)), 255)
                self.assertEqual(alpha.getpixel((4, cy)), 255)
                self.assertEqual(alpha.getpixel((sprite.width - 5, cy)), 255)

    def test_rotated_window_retains_its_cutout(self):
        for item in (37, 38, 318):
            with self.subTest(item=item):
                sprite, _ = wall(item)
                alpha = sprite.getchannel('A')
                cx = sprite.width // 2
                for y in (80, 90, 100):
                    self.assertEqual(alpha.getpixel((cx, y)), 0)
                for y in (50, 150):
                    self.assertEqual(alpha.getpixel((cx, y)), 255)

    def test_base_has_no_opaque_black_pixels(self):
        for item in (240, 38, 33, 922):
            sprite, _ = wall(item)
            for r, g, b, a in sprite.crop((0, sprite.height - 32, sprite.width, sprite.height)).getdata():
                if a:
                    self.assertGreater(max(r, g, b), 0, f'black base pixel in item {item}')

    def test_mask_cannot_create_coverage_or_destroy_partial_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            original = Image.new('RGBA', (4, 4))
            original.putpixel((1, 1), (90, 80, 70, 128))
            original.save(path / 'sprite.png')
            Image.new('RGBA', (4, 4), (255, 255, 255, 255)).save(path / 'mask.png')
            manifest = {'entries': {'static/west': {'textures': ['sprite.png']}}}
            apply_alpha_mask_to_textures(manifest, path, path / 'mask.png')
            with Image.open(path / 'sprite.png') as result:
                self.assertEqual(list(result.getdata()), list(original.getdata()))

    def test_odd_crop_preserves_exact_world_placement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            sprite = Image.new('RGBA', (12, 12))
            sprite.paste((80, 90, 100, 255), (2, 3, 7, 10))
            sprite.save(path / 'sprite.png')
            entry = {'textures': ['sprite.png'], 'crop': {'x': 0, 'y': 0}, 'anchor': {'x': 6.0, 'y': 8.0}}
            crop_rendered_textures_to_alpha({'entries': {'static/west': entry}}, path, True)
            with Image.open(path / 'sprite.png') as result:
                self.assertEqual(result.width, 6)
                self.assertEqual(result.width // 2 - entry['offsetX'], 4)
                self.assertEqual(result.height + entry['offsetY'], 5)
                self.assertEqual(result.getchannel('A').getbbox(), (0, 0, 5, 7))


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--preview':
        background = Image.new('RGBA', (640, 512), (90, 110, 100, 255))
        background.alpha_composite(assembly())
        background.save(sys.argv[2])
    else:
        unittest.main()
