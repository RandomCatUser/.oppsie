import os
import sys
import tempfile
import shutil
import unittest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.guibackup import load_image_from_path


class TestGuiLoader(unittest.TestCase):
    def test_load_image_from_path_supports_oppsie(self):
        temp_dir = tempfile.mkdtemp()
        try:
            src_path = os.path.join(temp_dir, "sample.png")
            img = Image.new("RGB", (7, 5), (12, 34, 56))
            img.save(src_path)

            oppsie_path = os.path.join(temp_dir, "sample.oppsie")
            from converter.to_oppsie import convert_to_oppsie
            convert_to_oppsie(src_path, oppsie_path)

            loaded = load_image_from_path(oppsie_path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.size, (7, 5))
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
