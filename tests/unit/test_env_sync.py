"""Keep the unit-test environment on the same package versions as the workflow.

The unit tests exercise the workflow scripts directly, so they must run on the
package versions that the workflow itself runs on. Those are locked in the
generated ``workflow/envs/module.<platform>.pin.txt`` files; the pixi
``test-unit`` feature mirrors them with exact ``X.Y.Z.*`` pins.
"""

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
ENV_DIR = REPO_ROOT / "workflow" / "envs"


def _test_unit_pins():
    with (REPO_ROOT / "pixi.toml").open("rb") as f:
        deps = tomllib.load(f)["feature"]["test-unit"]["dependencies"]
    return {name: spec for name, spec in deps.items() if name != "pytest"}


# Runtime tools that no script imports and that the unit tests do not need.
NON_PYTHON_TOOLS = {"curl"}


def _module_dependencies():
    text = (ENV_DIR / "module.yaml").read_text()
    return set(re.findall(r"^- ([a-z0-9_-]+) ", text, re.M)) - NON_PYTHON_TOOLS


def test_test_unit_covers_module_dependencies():
    """Every runtime dependency of the workflow is pinned for the unit tests."""
    assert _module_dependencies() <= set(_test_unit_pins())


@pytest.mark.parametrize("pin_file", sorted(ENV_DIR.glob("module.*.pin.txt")))
def test_test_unit_pins_match_module_pins(pin_file):
    """The exact test-unit pins equal the versions locked for the workflow."""
    locked = pin_file.read_text()
    for name, spec in _test_unit_pins().items():
        version = spec.removesuffix(".*")
        assert re.search(rf"/{re.escape(name)}-{re.escape(version)}-", locked), (
            f"{name} {spec} in pixi.toml is not the version locked in {pin_file.name}"
        )
