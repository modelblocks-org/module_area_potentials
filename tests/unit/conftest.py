"""Pytest configuration for the unit test suite.

Makes the workflow scripts importable (they are plain scripts, not a package)
and provides the reference-data machinery: tests compare computed outputs
against files committed under ``tests/reference/unit/``, which are regenerated
with ``pytest tests/unit --update-reference`` (``pixi run update-reference-unit``).
"""

import os
import sys
from pathlib import Path

# Scripts import matplotlib.pyplot at import time; force a headless backend
# before any of them is imported.
os.environ.setdefault("MPLBACKEND", "Agg")

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "workflow" / "scripts"))

import fixtures  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
import yaml  # noqa: E402

REFERENCE_DIR = REPO_ROOT / "tests" / "reference" / "unit"


def pytest_addoption(parser):
    """Add the --update-reference flag."""
    parser.addoption(
        "--update-reference",
        action="store_true",
        default=False,
        help="Write reference data from current outputs instead of comparing against it.",
    )


class ReferenceComparer:
    """Compares computed outputs against committed reference files."""

    def __init__(self, update):
        """If ``update`` is True, checks write reference files instead of comparing."""
        self.update = update

    def check_arrays(self, name, arrays, rtol=1e-6, atol=0.0):
        """Compare a dict of named arrays against ``<name>.npz`` reference data.

        Integer arrays must match exactly. Floating-point arrays are compared
        with a small relative tolerance because the reference data is generated
        on one platform but compared on all CI platforms, whose libm/SIMD
        implementations of log/sin and GDAL warps differ in the last ulp.
        """
        path = REFERENCE_DIR / f"{name}.npz"
        arrays = {key: np.asarray(value) for key, value in arrays.items()}
        if self.update:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path, **arrays)
            return
        assert path.exists(), (
            f"Missing reference file {path}. Generate it with: pixi run update-reference-unit"
        )
        stored = np.load(path)
        assert set(stored.files) == set(arrays), (
            f"{name}: array names differ from reference: "
            f"{sorted(arrays)} vs {sorted(stored.files)}"
        )
        for key, actual in arrays.items():
            is_float = np.issubdtype(actual.dtype, np.floating)
            np.testing.assert_allclose(
                actual,
                stored[key],
                rtol=rtol if is_float else 0.0,
                atol=atol if is_float else 0.0,
                equal_nan=True,
                err_msg=f"{name}:{key} differs from reference data",
            )

    def check_dataframe(self, name, csv_path, rtol=0.0):
        """Compare a CSV file produced by a test against ``<name>.csv`` reference data."""
        path = REFERENCE_DIR / f"{name}.csv"
        if self.update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(Path(csv_path).read_text())
            return
        assert path.exists(), (
            f"Missing reference file {path}. Generate it with: pixi run update-reference-unit"
        )
        actual = pd.read_csv(csv_path, index_col=0)
        stored = pd.read_csv(path, index_col=0)
        pd.testing.assert_frame_equal(
            actual, stored, check_exact=rtol == 0.0, rtol=rtol or 1e-15
        )


@pytest.fixture(scope="session")
def reference(request):
    """Reference-data comparer honouring the --update-reference flag."""
    return ReferenceComparer(update=request.config.getoption("--update-reference"))


@pytest.fixture(scope="session")
def world(tmp_path_factory):
    """Paths to the deterministic synthetic input dataset."""
    return fixtures.write_world(tmp_path_factory.mktemp("world"))


@pytest.fixture(scope="session")
def wdpa_raster_path(world, tmp_path_factory):
    """Protected-areas raster produced by the clip_and_rasterise_polys CLI."""
    from clip_and_rasterise_polys import clip_and_rasterise_polys

    path = tmp_path_factory.mktemp("wdpa") / "wdpa.tif"
    fixtures.run_cli(
        clip_and_rasterise_polys,
        [world["shapes"], world["landcover"], world["protected"], path],
    )
    return path


@pytest.fixture(scope="session")
def resampled_path(world, wdpa_raster_path, tmp_path_factory):
    """Resampled input NetCDF produced by the resample CLI."""
    from resample import resample_inputs

    directory = tmp_path_factory.mktemp("resampled")
    path = directory / "resampled.nc"
    fixtures.run_cli(
        resample_inputs,
        [
            world["shapes"],
            world["landcover"],
            world["slope"],
            world["settlement"],
            world["bathymetry"],
            wdpa_raster_path,
            yaml.dump(fixtures.LAND_COVER_TYPES),
            path,
            "--ship-travel-path",
            world["ship_travel"],
        ],
    )
    return path
