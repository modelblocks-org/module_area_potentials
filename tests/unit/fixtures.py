"""Deterministic synthetic geodata used by the unit tests.

All builders are seeded so that repeated test runs (and the committed reference
data) are reproducible. The geography is a small area near the Dutch coast:
two abutting land regions and one maritime region, with input rasters at
resolutions mimicking the real datasets (land cover 10 arcsec as the reference
grid; slope finer; settlement and bathymetry coarser).
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import rioxarray  # noqa: F401  # activates the .rio accessor
import xarray as xr
import yaml
from click.testing import CliRunner
from resample import GLOBCOVER_TYPES
from shapely.geometry import box

REPO_ROOT = Path(__file__).parent.parent.parent
LAND_COVER_TYPES = yaml.safe_load(
    (REPO_ROOT / "workflow" / "internal" / "settings.yaml").read_text()
)["land_cover_types"]

# Three abutting regions of 0.05 x 0.1 degrees: two land, one maritime.
SHAPES_BOUNDS = (5.0, 52.0, 5.15, 52.1)
LANDCOVER_RESOLUTION = 1 / 360  # 10 arcsec, like GlobCover
SLOPE_RESOLUTION = 1 / 450
SETTLEMENT_RESOLUTION = 1 / 120  # 30 arcsec, like GHSL
BATHYMETRY_RESOLUTION = 1 / 240  # 15 arcsec, like GEBCO
SHIP_TRAVEL_RESOLUTION = 1 / 200
SLOPE_NODATA = -32768
SHIP_TRAVEL_NODATA = -1.0


def run_cli(command, args):
    """Invoke a click command in-process and assert it succeeded."""
    result = CliRunner().invoke(
        command, [str(arg) for arg in args], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    return result


def make_shapes(include_subpixel_region=False):
    """Return the region shapes as a GeoDataFrame matching ShapesSchema."""
    records = [
        ("region_a", "AAA", "land", box(5.0, 52.0, 5.05, 52.1)),
        ("region_b", "AAA", "land", box(5.05, 52.0, 5.1, 52.1)),
        ("region_sea", "AAA", "maritime", box(5.1, 52.0, 5.15, 52.1)),
    ]
    if include_subpixel_region:
        # Far smaller than one land-cover pixel and placed away from any pixel
        # center, so rasterisation burns no pixels for it.
        records.append(
            ("region_tiny", "AAA", "land", box(5.12, 52.05, 5.1201, 52.0501))
        )
    shape_ids, country_ids, shape_classes, geometries = zip(*records)
    return gpd.GeoDataFrame(
        {
            "shape_id": list(shape_ids),
            "country_id": list(country_ids),
            "shape_class": list(shape_classes),
            "parent_name": [f"Parent of {shape_id}" for shape_id in shape_ids],
            "geometry": list(geometries),
        },
        crs="EPSG:4326",
    )


def grid_coords(resolution, pad_pixels=0, bounds=SHAPES_BOUNDS):
    """Return (x, y) pixel-center coordinates covering ``bounds`` plus padding."""
    xmin, ymin, xmax, ymax = bounds
    pad = pad_pixels * resolution
    x = np.arange(xmin - pad + resolution / 2, xmax + pad, resolution)
    y = np.arange(ymax + pad - resolution / 2, ymin - pad, -resolution)
    return x, y


def make_raster(values, x, y, nodata=None):
    """Wrap a 2D array into a (band, y, x) DataArray with CRS EPSG:4326."""
    da = xr.DataArray(
        np.asarray(values)[np.newaxis, ...],
        coords={"band": [1], "y": y, "x": x},
        dims=("band", "y", "x"),
    )
    da.rio.write_crs("EPSG:4326", inplace=True)
    if nodata is not None:
        da.rio.write_nodata(nodata, inplace=True)
    return da


def make_landcover(rng):
    """Random land cover raster guaranteed to contain every GlobCover code.

    Also contains the code 13, which is not a valid GlobCover code, to pin down
    how unmapped codes are treated (they belong to no category).
    """
    codes = np.array(sorted(GLOBCOVER_TYPES) + [13], dtype=np.uint8)
    x, y = grid_coords(LANDCOVER_RESOLUTION, pad_pixels=3)
    values = rng.choice(codes, size=(len(y), len(x))).astype(np.uint8)
    values[0, : len(codes)] = codes
    return make_raster(values, x, y)


def make_slope(rng):
    """Random slope raster: int16 slope * 100, like GEDTM30, with nodata holes."""
    x, y = grid_coords(SLOPE_RESOLUTION, pad_pixels=3)
    values = rng.integers(0, 3000, size=(len(y), len(x))).astype(np.int16)
    values[rng.random(values.shape) < 0.05] = SLOPE_NODATA
    return make_raster(values, x, y, nodata=SLOPE_NODATA)


def make_settlement(rng):
    """Random settlement raster: built-up surface in m2 per pixel, like GHSL."""
    x, y = grid_coords(SETTLEMENT_RESOLUTION, pad_pixels=3)
    values = rng.uniform(0, 500_000, size=(len(y), len(x))).astype(np.float32)
    values[rng.random(values.shape) < 0.6] = 0.0
    return make_raster(values, x, y)


def make_bathymetry(rng):
    """Random bathymetry raster: int16 elevation in m, like GEBCO."""
    x, y = grid_coords(BATHYMETRY_RESOLUTION, pad_pixels=3)
    values = rng.integers(-80, 40, size=(len(y), len(x))).astype(np.int16)
    return make_raster(values, x, y)


def make_ship_travel(rng):
    """Random ship traffic density raster (AIS position counts) with nodata."""
    x, y = grid_coords(SHIP_TRAVEL_RESOLUTION, pad_pixels=3)
    values = rng.integers(0, 50_000, size=(len(y), len(x))).astype(np.float32)
    values[rng.random(values.shape) < 0.3] = 0.0
    values[rng.random(values.shape) < 0.05] = SHIP_TRAVEL_NODATA
    return make_raster(values, x, y, nodata=SHIP_TRAVEL_NODATA)


def make_protected_areas():
    """Two protected-area polygons inside region_a."""
    return gpd.GeoDataFrame(
        {
            "site_name": ["site_1", "site_2"],
            "geometry": [
                box(5.005, 52.010, 5.020, 52.040),
                box(5.025, 52.050, 5.040, 52.090),
            ],
        },
        crs="EPSG:4326",
    )


def write_world(directory):
    """Write the full synthetic input dataset and return a dict of paths."""
    directory = Path(directory)
    rng = np.random.default_rng(20260707)
    paths = {
        "shapes": directory / "shapes.parquet",
        "landcover": directory / "landcover.tif",
        "slope": directory / "slope.tif",
        "settlement": directory / "settlement.tif",
        "bathymetry": directory / "bathymetry.tif",
        "ship_travel": directory / "ship_travel.tif",
        "protected": directory / "protected.gpkg",
    }
    make_shapes().to_parquet(paths["shapes"])
    make_landcover(rng).rio.to_raster(paths["landcover"])
    make_slope(rng).rio.to_raster(paths["slope"])
    make_settlement(rng).rio.to_raster(paths["settlement"])
    make_bathymetry(rng).rio.to_raster(paths["bathymetry"])
    make_ship_travel(rng).rio.to_raster(paths["ship_travel"])
    make_protected_areas().to_file(paths["protected"], driver="GPKG")
    return paths
