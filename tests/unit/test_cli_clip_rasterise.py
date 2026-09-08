"""Reference tests for the clip_and_rasterise_polys CLI.

Guards the planned switch to bbox-filtered vector reading: the output raster
for the synthetic protected areas must stay identical.
"""

import fixtures
import geopandas as gpd
import numpy as np
import rioxarray as rxr
from clip_and_rasterise_polys import clip_and_rasterise_polys


def test_wdpa_raster_reference(wdpa_raster_path, reference):
    """The rasterised protected areas match the committed reference data."""
    da = rxr.open_rasterio(wdpa_raster_path)
    reference.check_arrays(
        "wdpa_raster", {"values": da.values, "x": da.x.values, "y": da.y.values}
    )


def test_wdpa_raster_marks_protected_pixels(wdpa_raster_path, world):
    """Pixels inside the protected polygons carry values from the reference raster."""
    da = rxr.open_rasterio(wdpa_raster_path).squeeze(drop=True)
    # Pixel centers inside the first protected polygon (5.005..5.020, 52.010..52.040)
    inside = da.sel(x=slice(5.006, 5.019), y=slice(52.039, 52.011))
    assert inside.size > 0
    assert np.count_nonzero(inside.values) == inside.size


def test_wdpa_raster_reprojected_source(world, tmp_path):
    """Polygons in another CRS give the same raster (boxes stay boxes in Mercator)."""
    reprojected = tmp_path / "protected_3857.gpkg"
    gpd.read_file(world["protected"]).to_crs("EPSG:3857").to_file(
        reprojected, driver="GPKG"
    )
    fixtures.run_cli(
        clip_and_rasterise_polys,
        [world["shapes"], world["landcover"], reprojected, tmp_path / "wdpa.tif"],
    )
    fixtures.run_cli(
        clip_and_rasterise_polys,
        [world["shapes"], world["landcover"], world["protected"], tmp_path / "ref.tif"],
    )
    np.testing.assert_array_equal(
        rxr.open_rasterio(tmp_path / "wdpa.tif").values,
        rxr.open_rasterio(tmp_path / "ref.tif").values,
    )
