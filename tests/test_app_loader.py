import os
import sys
import shutil
import tempfile
import unittest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import human_size, load_image
from converter.to_oppsie import convert_to_oppsie


class TestAppLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _make_oppsie(self, size, color):
        src_path = os.path.join(self.temp_dir, "sample.png")
        Image.new("RGB", size, color).save(src_path)
        oppsie_path = os.path.join(self.temp_dir, "sample.oppsie")
        convert_to_oppsie(src_path, oppsie_path)
        return src_path, oppsie_path

    def test_load_image_supports_oppsie(self):
        _, oppsie_path = self._make_oppsie((6, 6), (10, 20, 30))

        loaded = load_image(oppsie_path)

        self.assertEqual(loaded.size, (6, 6))
        self.assertEqual(loaded.getpixel((0, 0))[:3], (10, 20, 30))

    def test_load_image_supports_standard_formats(self):
        src_path, _ = self._make_oppsie((6, 6), (10, 20, 30))

        loaded = load_image(src_path)

        self.assertEqual(loaded.size, (6, 6))

    def test_load_image_strips_quotes_from_path(self):
        _, oppsie_path = self._make_oppsie((4, 3), (1, 2, 3))

        loaded = load_image(f'"{oppsie_path}"')

        self.assertEqual(loaded.size, (4, 3))

    def test_human_size(self):
        self.assertEqual(human_size(512), "512.0 B")
        self.assertEqual(human_size(2048), "2.0 KB")
        self.assertEqual(human_size(5 * 1024 * 1024), "5.0 MB")


if __name__ == "__main__":
    unittest.main()
