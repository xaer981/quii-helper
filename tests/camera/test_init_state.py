import unittest

from quii_helper.camera.settings.init_state import (
    CAMERA_CONFIG_KWARG_NAMES,
    camera_config_kwargs,
)


class CameraInitStateTests(unittest.TestCase):
    def test_camera_config_kwargs_filters_only_config_override_names(
        self,
    ) -> None:
        values = {
            name: f"value-{index}"
            for index, name in enumerate(CAMERA_CONFIG_KWARG_NAMES)
        }
        values.update(
            {
                "self": object(),
                "config": object(),
                "preview_settings": object(),
                "data_dir": "data",
                "emit": object(),
                "status": object(),
            }
        )

        kwargs = camera_config_kwargs(values)

        self.assertEqual(set(CAMERA_CONFIG_KWARG_NAMES), set(kwargs))
        self.assertNotIn("self", kwargs)
        self.assertNotIn("preview_settings", kwargs)
        self.assertEqual("value-0", kwargs[CAMERA_CONFIG_KWARG_NAMES[0]])

    def test_camera_config_kwargs_requires_complete_init_locals(self) -> None:
        with self.assertRaises(KeyError):
            camera_config_kwargs({})


if __name__ == "__main__":
    unittest.main()
