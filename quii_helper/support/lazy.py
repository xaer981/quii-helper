from collections.abc import Mapping
from importlib import import_module
from typing import Any, Callable

LazyExports = Mapping[str, tuple[str, str | None]]


def lazy_getattr(
    package_name: str,
    exports: LazyExports,
    module_globals: dict[str, Any],
):
    def __getattr__(name: str) -> Any:
        try:
            module_name, attr_name = exports[name]
        except KeyError as exc:
            raise AttributeError(
                f"module {package_name!r} has no attribute {name!r}"
            ) from exc
        module = import_module(module_name)
        value = module if attr_name is None else getattr(module, attr_name)
        module_globals[name] = value
        return value

    return __getattr__


def lazy_exports(
    package_name: str,
    exports: LazyExports,
    module_globals: dict[str, Any],
) -> tuple[list[str], Callable[[str], Any]]:
    return sorted(exports), lazy_getattr(package_name, exports, module_globals)
