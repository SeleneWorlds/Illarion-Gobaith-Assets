"""Regression checks for scene-frame animations and static sprite export."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from sprite_pipeline import (
    build_visual_json,
    crop_rendered_textures_to_alpha,
    load_model_config_from_raw,
)


class SceneAnimationTests(unittest.TestCase):
    def test_frame_range_validation(self):
        root = Path(__file__).resolve().parent.parent
        path = root / 'models/structures/campfire/campfire.json'
        base = dict(model='campfire.blend', sprites='illarion/items/item_12', visual='items/item_12')
        config = load_model_config_from_raw(path, {**base, 'frameRange': [33, 64]}, root)
        self.assertEqual(config.frame_range, (33, 64))
        self.assertIsNone(load_model_config_from_raw(path, base, root).frame_range)
        for value in ([0, 4], [4, 3], [True, 4], [1.5, 4], [1], '1,4'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_model_config_from_raw(path, {**base, 'frameRange': value}, root)
        with self.assertRaises(ValueError):
            load_model_config_from_raw(path, {**base, 'frameRange': [1, 4], 'animations': ['Idle']}, root)

    def test_animation_has_shared_crop_anchor_and_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i, box in enumerate([(3, 8, 9, 15), (6, 2, 13, 15)]):
                image = Image.new('RGBA', (16, 16))
                image.paste((255, 100, 0, 255), box)
                image.save(root / f'{i}.png')
            manifest = {'fps': 24, 'entries': {'static/south': {
                'textures': ['0.png', '1.png'], 'offsetX': 0, 'offsetY': 0,
                'crop': {'x': 0, 'y': 0, 'width': 16, 'height': 16},
                'anchor': {'x': 8, 'y': 15},
            }}}
            cropped = crop_rendered_textures_to_alpha(manifest, root)
            visual = build_visual_json(cropped, root, root)
            self.assertEqual(visual['type'], 'animated')
            self.assertEqual(visual['duration'], 2 / 24)
            self.assertEqual(visual['textures'], ['0.png', '1.png'])
            for filename in visual['textures']:
                with Image.open(root / filename) as image:
                    self.assertEqual(image.size, (10, 13))
            self.assertEqual((visual['offsetX'], visual['offsetY']), (0, 0))
            cropped['entries']['static/south']['textures'] = ['0.png']
            static = build_visual_json(cropped, root, root)
            self.assertEqual(static['type'], 'simple')
            self.assertEqual(static['texture'], '0.png')


if __name__ == '__main__':
    unittest.main()
