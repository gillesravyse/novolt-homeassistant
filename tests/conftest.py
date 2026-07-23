"""Test setup: make the HA-free modules importable without homeassistant.

The package __init__ imports Home Assistant, so these modules are loaded
straight from their file paths — exactly the split that keeps the API client
portable and the payload logic testable without a Home Assistant install.
"""

import importlib.util
import pathlib
import sys

_COMPONENT = pathlib.Path(__file__).parent.parent / "custom_components" / "novolt"


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, _COMPONENT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


novolt_api = _load("novolt_api", "api.py")
novolt_derive = _load("novolt_derive", "derive.py")
