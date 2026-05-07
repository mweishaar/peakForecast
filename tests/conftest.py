"""Make peak_forecast.parser / .const importable without Home Assistant installed.

The real ``peak_forecast/__init__.py`` imports ``homeassistant.*`` at module load,
so we register a synthetic package object pointing at the same directory and
skip executing the real ``__init__.py``. Relative imports inside parser.py
(``from .const import ...``) still resolve correctly.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "peak_forecast"


def _install_synthetic_package() -> None:
    if "peak_forecast" in sys.modules:
        return
    pkg = ModuleType("peak_forecast")
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules["peak_forecast"] = pkg

    for submodule in ("const", "parser"):
        spec = importlib.util.spec_from_file_location(
            f"peak_forecast.{submodule}", PKG_DIR / f"{submodule}.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"peak_forecast.{submodule}"] = module
        spec.loader.exec_module(module)


_install_synthetic_package()
