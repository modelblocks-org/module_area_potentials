"""Subset to a bounding box and rasterise polygons."""

import click
import geopandas as gpd
import numpy as np
import rioxarray as rxr
import xarray as xr
from rasterio.features import geometry_mask
from shapely.geometry import box


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("reference_raster_path", type=str)
@click.argument("protected_area_path", type=str)
@click.argument("output_path", type=str)
def clip_and_rasterise_polys(
    shapes_path, reference_raster_path, protected_area_path, output_path
):
    """Rasterise the polygons in PROTECTED_AREA_PATH onto the grid of the reference raster.

    Only polygons intersecting the reference raster are read. The output is a
    0/1 uint8 raster on the full reference grid (1 = inside a polygon), saved
    to OUTPUT_PATH.
    """
    shapes = gpd.read_parquet(shapes_path)
    reference_raster = rxr.open_rasterio(reference_raster_path)

    # FIXME: read the right layer(s) and deal with both poly and point layers
    xmin, ymin, xmax, ymax = shapes.total_bounds
    # The bbox filter is pushed down to the driver's spatial index, so only
    # features that can possibly overlap the reference raster are read instead
    # of the entire (potentially multi-GB, global) dataset. Attribute columns
    # are skipped; only geometries are needed. Passing the bbox as a GeoSeries
    # (rather than a tuple) lets geopandas transform it into the dataset's own
    # CRS before filtering.
    bbox = gpd.GeoSeries(
        [box(*reference_raster.rio.bounds())], crs=reference_raster.rio.crs
    )
    protected_areas = gpd.read_file(
        protected_area_path, bbox=bbox, columns=[], use_arrow=True
    )
    print(f"Protected areas intersecting the reference raster: {len(protected_areas)}")
    protected_areas = protected_areas.to_crs(shapes.crs)
    protected_areas = protected_areas.cx[xmin:xmax, ymin:ymax]
    print(f"Protected areas after applying total_bounds: {len(protected_areas)}")

    # Burn the polygons into a 0/1 mask on the reference grid. rio.clip would
    # instead mask the (lazily opened) reference raster itself, materialising a
    # full-extent float64 copy of it; geometry_mask only ever holds one byte per
    # pixel. Resampling this mask with averaging yields the protected fraction.
    mask = geometry_mask(
        protected_areas.geometry,
        out_shape=reference_raster.rio.shape,
        transform=reference_raster.rio.transform(),
        invert=True,
    )
    protected_raster = xr.zeros_like(reference_raster, dtype=np.uint8)
    protected_raster.data[0] = mask
    protected_raster.rio.write_nodata(None, inplace=True)
    protected_raster.rio.to_raster(output_path, driver="GTiff", compress="LZW")


if __name__ == "__main__":
    clip_and_rasterise_polys()
