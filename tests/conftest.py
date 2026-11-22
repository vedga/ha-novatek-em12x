"""Test bootstrap: load novatek_em12x submodules without the HA-dependent __init__."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

PKG_DIR = Path(__file__).parent.parent / "custom_components" / "novatek_em12x"

pkg = types.ModuleType("novatek_em12x")
pkg.__path__ = [str(PKG_DIR)]
sys.modules.setdefault("novatek_em12x", pkg)

importlib.import_module("novatek_em12x.const")
importlib.import_module("novatek_em12x.api")
