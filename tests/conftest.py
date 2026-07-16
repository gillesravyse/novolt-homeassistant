"""Test setup: make the HA-free api module importable without homeassistant.

The package __init__ imports Home Assistant, so the client module is loaded
straight from its file path — exactly the split that lets it move to PyPI.
"""

import importlib.util
import pathlib
import sys

_API_PATH = (
    pathlib.Path(__file__).parent.parent / "custom_components" / "novolt" / "api.py"
)
_spec = importlib.util.spec_from_file_location("novolt_api", _API_PATH)
novolt_api = importlib.util.module_from_spec(_spec)
sys.modules["novolt_api"] = novolt_api
_spec.loader.exec_module(novolt_api)
