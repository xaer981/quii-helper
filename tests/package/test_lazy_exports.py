import unittest

from quii_helper.support.lazy import lazy_exports


class LazyExportsTests(unittest.TestCase):
    def test_lazy_exports_returns_sorted_all_and_caching_getattr(self) -> None:
        module_globals = {}
        exports = {
            "sqrt": ("math", "sqrt"),
            "math": ("math", None),
        }

        all_names, module_getattr = lazy_exports(
            "fake_package", exports, module_globals
        )

        self.assertEqual(["math", "sqrt"], all_names)
        sqrt = module_getattr("sqrt")
        math_module = module_getattr("math")
        self.assertIs(sqrt, module_globals["sqrt"])
        self.assertIs(math_module, module_globals["math"])
        self.assertEqual(3.0, sqrt(9))

    def test_lazy_exports_getattr_raises_attribute_error(self) -> None:
        _all_names, module_getattr = lazy_exports("fake_package", {}, {})

        with self.assertRaises(AttributeError):
            module_getattr("missing")


if __name__ == "__main__":
    unittest.main()
