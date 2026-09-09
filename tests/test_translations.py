"""Every entity the integration creates must have a name in every language.

This is not a style check. ``has_entity_name`` + a ``translation_key`` with no
translation behind it gives an entity with no name of its own: Home Assistant
falls back to the device name, so two nameless sensors on the same site device
are indistinguishable. It happened — ``ev_km_done``/``ev_km_remaining`` shipped
into the three translation files but not into ``strings.json``, which is the file
the translations are supposed to be generated from, so the next regeneration
would have silently taken both names away again.

Parsed out of the source rather than imported, because importing the platforms
needs Home Assistant and this is exactly the kind of mistake you want caught in
the cheap test run.
"""

from __future__ import annotations

import json
import pathlib
import re

COMPONENT = pathlib.Path(__file__).parent.parent / "custom_components" / "novolt"
PLATFORMS = {"sensor": "sensor.py", "binary_sensor": "binary_sensor.py"}
STRING_FILES = [
    COMPONENT / "strings.json",
    *sorted((COMPONENT / "translations").glob("*.json")),
]


def _translation_keys(filename: str) -> set[str]:
    source = (COMPONENT / filename).read_text()
    return set(re.findall(r'translation_key="([a-z0-9_]+)"', source)) | set(
        re.findall(r'_attr_translation_key = "([a-z0-9_]+)"', source)
    )


def test_every_translation_key_has_a_name_in_every_language() -> None:
    missing: list[str] = []
    for path in STRING_FILES:
        entity = json.loads(path.read_text())["entity"]
        for platform, filename in PLATFORMS.items():
            named = entity.get(platform, {})
            for key in sorted(_translation_keys(filename)):
                if not named.get(key, {}).get("name"):
                    missing.append(f"{path.name}: {platform}.{key}")
    assert not missing, "entities without a name: " + ", ".join(missing)


def test_translation_files_carry_the_same_keys_as_strings() -> None:
    """A language file that drifts from ``strings.json`` is a name nobody sees."""
    reference = json.loads((COMPONENT / "strings.json").read_text())["entity"]
    for path in STRING_FILES[1:]:
        entity = json.loads(path.read_text())["entity"]
        for platform in PLATFORMS:
            assert set(entity.get(platform, {})) == set(reference.get(platform, {})), (
                f"{path.name} disagrees with strings.json on {platform} keys"
            )
