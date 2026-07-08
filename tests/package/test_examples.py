import importlib


class ExampleModuleTests:
    def test_discover_env_values_module_is_importable(self) -> None:
        module = importlib.import_module("examples.discover_env_values")

        assert "/auth/user" == module.USERAUTH_PATH
        assert callable(module.main)
