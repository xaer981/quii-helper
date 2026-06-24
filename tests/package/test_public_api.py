import importlib
import unittest

import quii_helper
from quii_helper.support.root_exports import ROOT_EXPORTS

LAZY_EXPORT_PACKAGES = (
    "quii_helper",
    "quii_helper.cloud",
    "quii_helper.device",
    "quii_helper.diagnostics",
    "quii_helper.diagnostics.wrapped",
    "quii_helper.devtools",
    "quii_helper.direct",
    "quii_helper.io",
    "quii_helper.media",
    "quii_helper.preview",
    "quii_helper.protocols",
    "quii_helper.protocols.mqtt",
    "quii_helper.protocols.p2p",
    "quii_helper.protocols.quii",
    "quii_helper.protocols.rbudp",
    "quii_helper.protocols.tcp",
    "quii_helper.protocols.ust",
)


class PublicApiTests(unittest.TestCase):
    def test_root_exported_symbols_import(self) -> None:
        failures = []
        for name in quii_helper.__all__:
            try:
                getattr(quii_helper, name)
            except Exception as exc:  # pragma: no cover - failure details
                failures.append((name, type(exc).__name__, str(exc)))

        self.assertEqual([], failures)

    def test_root_all_matches_root_export_map(self) -> None:
        self.assertEqual(sorted(ROOT_EXPORTS), quii_helper.__all__)

    def test_lazy_export_packages_import_all_symbols(self) -> None:
        failures = []
        for package_name in LAZY_EXPORT_PACKAGES:
            package = importlib.import_module(package_name)
            for name in package.__all__:
                try:
                    getattr(package, name)
                except Exception as exc:  # pragma: no cover - failure details
                    failures.append(
                        (package_name, name, type(exc).__name__, str(exc))
                    )

        self.assertEqual([], failures)

    def test_camera_high_level_methods_exist(self) -> None:
        camera_cls = quii_helper.Camera
        for method_name in ("capture", "snapshot", "save_video", "record"):
            self.assertTrue(callable(getattr(camera_cls, method_name, None)))


if __name__ == "__main__":
    unittest.main()
