"""Unit tests for the UTM buffering helpers in _geo.py."""

import geopandas as gpd
import numpy as np
import pyproj
import pytest
from _geo import apply_utm_buffer, get_utm_crs_from_lonlat
from shapely.geometry import box

GEOD = pyproj.Geod(ellps="WGS84")


@pytest.mark.parametrize(
    ("lon", "lat", "epsg"),
    [
        (5.0, 52.0, 32631),
        # Norway exception: zone 32 is widened at 56-64N, so 5E is zone 32, not 31
        (5.0, 60.0, 32632),
        (5.0, -30.0, 32731),
        (-70.0, 45.0, 32619),
    ],
)
def test_get_utm_crs_from_lonlat(lon, lat, epsg):
    """The UTM zone (including the Norway exception) is selected per centroid."""
    assert get_utm_crs_from_lonlat(lon, lat).to_epsg() == epsg


def _geodesic_area(geom):
    """Unsigned geodesic area of a lon/lat geometry in m2."""
    area, _ = GEOD.geometry_area_perimeter(geom)
    return abs(area)


def test_apply_utm_buffer_grows_geometries():
    """Buffered geometries contain the originals and grow by roughly the right area."""
    gdf = gpd.GeoDataFrame(
        {"geometry": [box(5.0, 52.0, 5.1, 52.1), box(15.0, 48.0, 15.1, 48.1)]},
        crs="EPSG:4326",
    )
    distance = 10_000
    buffered = apply_utm_buffer(gdf, buffer_distance_m=distance)
    assert buffered.crs == gdf.crs
    for original, result in zip(gdf.geometry, buffered.geometry):
        assert result.contains(original)
        _, perimeter = GEOD.geometry_area_perimeter(original)
        expected_area = (
            _geodesic_area(original) + perimeter * distance + np.pi * distance**2
        )
        assert _geodesic_area(result) == pytest.approx(expected_area, rel=0.15)


def test_apply_utm_buffer_out_of_range_returns_none():
    """Geometries whose centroid has no UTM zone produce a warning and None."""
    gdf = gpd.GeoDataFrame({"geometry": [box(5.0, 85.0, 5.1, 85.1)]}, crs="EPSG:4326")
    with pytest.warns(UserWarning, match="Failed to buffer"):
        buffered = apply_utm_buffer(gdf)
    assert buffered.geometry.isna().all()
