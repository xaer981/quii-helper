import unittest
from pathlib import Path


class PackageLayoutTests(unittest.TestCase):
    def _package_py_files(self, *parts: str) -> list[str]:
        package_dir = Path(__file__).resolve().parents[2].joinpath(*parts)
        return sorted(path.name for path in package_dir.glob("*.py"))

    def test_feature_roots_keep_only_package_init_files(self) -> None:
        package_roots = [
            ("quii_helper", "camera"),
            ("quii_helper", "cloud"),
            ("quii_helper", "device"),
            ("quii_helper", "diagnostics", "wrapped"),
            ("quii_helper", "media"),
            ("quii_helper", "media", "h264"),
            ("quii_helper", "preview"),
            ("quii_helper", "preview", "outputs"),
            ("quii_helper", "preview", "processing"),
            ("quii_helper", "protocols", "p2p"),
            ("quii_helper", "protocols", "rbudp"),
            ("quii_helper", "protocols", "tcp"),
            ("quii_helper", "streaming"),
        ]
        for package_root in package_roots:
            with self.subTest(package_root=package_root):
                self.assertEqual(
                    ["__init__.py"],
                    self._package_py_files(*package_root),
                )

    def test_quii_helper_top_level_keeps_only_entrypoint_files(self) -> None:
        self.assertEqual(
            ["__init__.py", "main.py"],
            self._package_py_files("quii_helper"),
        )


if __name__ == "__main__":
    unittest.main()
