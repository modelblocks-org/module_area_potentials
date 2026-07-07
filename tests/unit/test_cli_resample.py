"""Reference tests for the resample.py CLI on the synthetic world.

This is the broadest guard for the resampling rewrite: it pins the variable
set, the reference grid, dtypes and every resampled value.
"""

import fixtures
import numpy as np
import pytest
import xarray as xr

EXPECTED_VARIABLES = {
    f"landcover_{category}" for category in set(fixtures.LAND_COVER_TYPES.values())
} | {
    "pixel_area",
    "regions",
    "regions_land",
    "regions_maritime",
    "slope_deg",
    "settlement_share",
    "settlement_area",
    "bathymetry",
    "protected",
    "ship_travel",
}


@pytest.fixture(scope="module")
def resampled(resampled_path):
    """The resampled dataset, loaded into memory."""
    with xr.open_dataset(resampled_path, decode_coords="all") as ds:
        return ds.load()


def test_resample_variable_set(resampled):
    """All expected variables are present."""
    assert set(resampled.data_vars) - {"spatial_ref"} == EXPECTED_VARIABLES


def test_resample_grid_is_landcover_grid(resampled):
    """The output grid is the land-cover grid clipped to the shapes' bounds."""
    xmin, ymin, xmax, ymax = fixtures.SHAPES_BOUNDS
    resolution = fixtures.LANDCOVER_RESOLUTION
    x = resampled.x.values
    y = resampled.y.values
    assert np.allclose(np.diff(x), resolution)
    assert np.allclose(np.diff(y), -resolution)
    # clip_box keeps pixels that merely touch the bounds, so pixel centers may
    # lie up to one resolution step outside them.
    assert abs(x.min() - xmin) <= resolution
    assert abs(x.max() - xmax) <= resolution
    assert abs(y.min() - ymin) <= resolution
    assert abs(y.max() - ymax) <= resolution


def test_resample_region_masks(resampled):
    """Land/maritime masks are 1 inside their regions and NaN elsewhere."""
    regions = resampled["regions"].values
    land = resampled["regions_land"].values
    maritime = resampled["regions_maritime"].values
    # regions 0 and 1 are land, region 2 is maritime (fixture ordering)
    assert (land[np.isin(regions, [0.0, 1.0])] == 1).all()
    assert np.isnan(land[regions == 2.0]).all()
    assert (maritime[regions == 2.0] == 1).all()
    assert np.isnan(maritime[np.isin(regions, [0.0, 1.0])]).all()


def test_resample_reference_values(resampled, reference):
    """Every resampled variable matches the committed reference data."""
    arrays = {name: resampled[name].values for name in sorted(resampled.data_vars)}
    arrays["x"] = resampled.x.values
    arrays["y"] = resampled.y.values
    reference.check_arrays("resample_output", arrays)


# On-disk dtypes as written by the current pipeline (queried with
# mask_and_scale=False). Any change here is a deliberate storage change.
ON_DISK_DTYPES = {
    "bathymetry": "float32",
    "pixel_area": "float32",
    "protected": "float32",
    "regions": "float32",
    "regions_land": "int8",
    "regions_maritime": "int8",
    "settlement_area": "float32",
    "settlement_share": "float32",
    "ship_travel": "float32",
    "slope_deg": "float32",
} | {
    f"landcover_{category}": "int8"
    for category in set(fixtures.LAND_COVER_TYPES.values())
}


def test_resample_on_disk_dtypes(resampled_path):
    """Variables are stored on disk with the documented dtypes."""
    with xr.open_dataset(resampled_path, mask_and_scale=False) as ds:
        actual = {name: str(ds[name].dtype) for name in ds.data_vars}
    actual.pop("spatial_ref", None)
    assert actual == ON_DISK_DTYPES
