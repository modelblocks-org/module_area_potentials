"""Unit tests for the pure functions in resample.py.

These pin down current behaviour so that performance rewrites (land-cover
lookup table, vectorised pixel areas) can be verified to be output-preserving.
"""

import fixtures
import geopandas as gpd
import numpy as np
import pyproj
import pytest
import xarray as xr
from resample import (
    GLOBCOVER_TYPES,
    _rasterize_regions,
    aggregate_land_cover_types,
    determine_pixel_areas,
)
from shapely.geometry import box


def _landcover_da(values):
    """Wrap a 2D uint8 array into a (band, y, x) DataArray like open_rasterio."""
    values = np.asarray(values, dtype=np.uint8)
    height, width = values.shape
    return xr.DataArray(
        values[np.newaxis, ...],
        coords={
            "band": [1],
            "y": np.arange(height, dtype=float),
            "x": np.arange(width, dtype=float),
        },
        dims=("band", "y", "x"),
    )


def _expected_masks(values, mapping):
    """Independent oracle: per-category membership masks via np.isin."""
    expected = {}
    for category in sorted(set(mapping.values())):
        codes = [
            code for code, name in GLOBCOVER_TYPES.items() if mapping[name] == category
        ]
        expected[category] = np.isin(values, codes).astype(np.int8)
    return expected


def test_aggregate_land_cover_types_all_codes():
    """Every GlobCover code lands in exactly the category configured for it."""
    codes = np.array(sorted(GLOBCOVER_TYPES), dtype=np.uint8)
    values = np.tile(codes, (3, 1))
    result = aggregate_land_cover_types(
        _landcover_da(values), fixtures.LAND_COVER_TYPES
    )
    expected = _expected_masks(values, fixtures.LAND_COVER_TYPES)
    assert set(result.data_vars) == set(expected)
    for category, mask in expected.items():
        np.testing.assert_array_equal(np.squeeze(result[category].values), mask)
        assert result[category].dtype == np.int8


def test_aggregate_land_cover_types_unmapped_code():
    """Codes not in GLOBCOVER_TYPES (here: 13) belong to no category."""
    values = np.array([[13, 11, 13], [13, 13, 210]], dtype=np.uint8)
    result = aggregate_land_cover_types(
        _landcover_da(values), fixtures.LAND_COVER_TYPES
    )
    total = sum(np.squeeze(result[var].values) for var in result.data_vars)
    np.testing.assert_array_equal(total, np.array([[0, 1, 0], [0, 0, 1]]))


def test_aggregate_land_cover_types_empty_category():
    """A configured category with no pixels yields an all-zero mask."""
    values = np.full((4, 4), 14, dtype=np.uint8)  # RAINFED_CROPLANDS -> FARM
    result = aggregate_land_cover_types(
        _landcover_da(values), fixtures.LAND_COVER_TYPES
    )
    assert np.squeeze(result["FARM"].values).all()
    for category in set(fixtures.LAND_COVER_TYPES.values()) - {"FARM"}:
        assert not result[category].values.any()


@pytest.mark.parametrize("seed", range(5))
def test_aggregate_land_cover_types_randomized(seed):
    """Random rasters (including unmapped codes) match the np.isin oracle."""
    rng = np.random.default_rng(seed)
    codes = np.array(sorted(GLOBCOVER_TYPES) + [13, 255], dtype=np.uint8)
    values = rng.choice(codes, size=(17, 23))
    result = aggregate_land_cover_types(
        _landcover_da(values), fixtures.LAND_COVER_TYPES
    )
    for category, mask in _expected_masks(values, fixtures.LAND_COVER_TYPES).items():
        np.testing.assert_array_equal(np.squeeze(result[category].values), mask)


def test_aggregate_land_cover_types_custom_mapping():
    """The mapping argument is respected, not just the internal defaults."""
    mapping = {
        name: ("LOW" if code < 100 else "HIGH")
        for code, name in GLOBCOVER_TYPES.items()
    }
    rng = np.random.default_rng(7)
    values = rng.choice(np.array(sorted(GLOBCOVER_TYPES), dtype=np.uint8), size=(9, 9))
    result = aggregate_land_cover_types(_landcover_da(values), mapping)
    assert set(result.data_vars) == {"LOW", "HIGH"}
    for category, mask in _expected_masks(values, mapping).items():
        np.testing.assert_array_equal(np.squeeze(result[category].values), mask)


def _pixel_area_raster(resolution=0.5):
    """A raster spanning 60N..60S used for pixel-area tests."""
    x = np.arange(0, 2, resolution) + resolution / 2
    y = np.arange(60, -60, -resolution) - resolution / 2
    values = np.ones((len(y), len(x)), dtype=np.int8)
    return fixtures.make_raster(values, x, y)


def test_determine_pixel_areas_matches_geodesic():
    """Pixel areas agree with exact geodesic areas from pyproj at various latitudes."""
    resolution = 0.5
    raster = _pixel_area_raster(resolution)
    pixel_area = determine_pixel_areas(raster)
    geod = pyproj.Geod(ellps="WGS84")
    for lat in [59.75, 45.25, 0.25, -45.25, -59.75]:
        # Densify the cell outline: pyproj measures geodesic edges, while the
        # pixel is bounded by parallels, which are not geodesics.
        cell = box(
            0, lat - resolution / 2, resolution, lat + resolution / 2
        ).segmentize(resolution / 100)
        expected_m2, _ = geod.geometry_area_perimeter(cell)
        actual_m2 = float(pixel_area.sel(y=lat))
        assert actual_m2 == pytest.approx(abs(expected_m2), rel=1e-6)


def test_determine_pixel_areas_north_south_symmetric():
    """Pixel areas are symmetric about the equator."""
    pixel_area = determine_pixel_areas(_pixel_area_raster())
    north = pixel_area.sel(y=45.25)
    south = pixel_area.sel(y=-45.25)
    assert float(north) == pytest.approx(float(south), rel=1e-12)


def test_determine_pixel_areas_requires_wgs84():
    """Non-WGS84 rasters are rejected."""
    raster = _pixel_area_raster()
    raster = raster.rio.write_crs("EPSG:3857")
    with pytest.raises(AssertionError, match="EPSG:4326"):
        determine_pixel_areas(raster)


def test_rasterize_regions():
    """Region indices are burned into the raster; uncovered pixels are NaN."""
    resolution = 0.1
    x = np.arange(0, 1, resolution) + resolution / 2
    y = np.arange(1, 0, -resolution) - resolution / 2
    reference = fixtures.make_raster(np.ones((len(y), len(x)), dtype=np.int8), x, y)
    shapes = gpd.GeoDataFrame(
        {"geometry": [box(0, 0, 0.4, 1), box(0.6, 0, 1, 1)]}, crs="EPSG:4326"
    )
    result = _rasterize_regions(shapes, reference)
    assert result.dtype == np.float32
    assert result.shape == (10, 10)
    np.testing.assert_array_equal(result[:, :4], 0.0)
    np.testing.assert_array_equal(result[:, 6:], 1.0)
    assert np.isnan(result[:, 4:6]).all()
