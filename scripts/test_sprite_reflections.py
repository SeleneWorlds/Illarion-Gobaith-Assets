import json
from pathlib import Path
import tempfile
import unittest

from sprite_pipeline import load_model_config_from_raw, load_variant_configs


class ReflectionConfigTests(unittest.TestCase):
    def config(self, **overrides):
        raw = {"sprites": "illarion/items/test", "visual": "items/test", **overrides}
        return load_model_config_from_raw(Path("/tmp/model.json"), raw, Path("/tmp"))

    def test_existing_configs_keep_original_lighting(self):
        self.assertEqual(self.config().reflections, "none")

    def test_studio_is_opt_in(self):
        self.assertEqual(self.config(reflections="studio").reflections, "studio")

    def test_invalid_presets_and_types_are_rejected(self):
        for value in ("unknown", "STUDIO", True, 1, None, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "reflections"):
                self.config(reflections=value)

    def test_variants_inherit_and_can_disable_studio(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.json"
            path.write_text(json.dumps({
                "type": "variants",
                "sprites": "illarion/items/test",
                "visual": "items/test",
                "reflections": "studio",
                "variants": [{}, {"reflections": "none"}],
            }))
            _, variants = load_variant_configs(path, Path(folder))
            self.assertEqual([v.model.reflections for v in variants], ["studio", "none"])


if __name__ == "__main__":
    unittest.main()
