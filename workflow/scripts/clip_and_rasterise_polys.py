"""Rasterise protected-area polygons onto the grid of a reference raster."""

import click
import geopandas as gpd
import numpy as np
import pyogrio
import pyproj
import rioxarray as rxr
import shapely
import xarray as xr
from rasterio.features import geometry_mask
from rasterio.warp import transform_bounds

# Features per Arrow batch: bounds the memory of the streaming rasterisation
# (a few thousand WDPA polygons are at most a few hundred MB of geometries).
BATCH_SIZE = 5000


def rasterise_polygons(polygons_path, reference_raster, batch_size=BATCH_SIZE):
    """Burn the polygons intersecting the reference grid into a 0/1 mask.

    Only features intersecting the reference bounds are read (the driver's
    spatial index does the filtering), only their geometries (no attribute
    columns), and they are streamed in Arrow batches: each batch is burned
    into the shared mask and released, so memory stays bounded by one batch
    instead of holding every intersecting polygon at once (over Europe the
    global WDPA has ~150,000 of them). Polygons are reprojected if the layer's
    CRS differs from the raster's.
    """
    raster_crs = pyproj.CRS.from_user_input(reference_raster.rio.crs)
    layer_crs = pyproj.CRS.from_user_input(pyogrio.read_info(polygons_path)["crs"])
    bbox = transform_bounds(
        raster_crs, layer_crs, *reference_raster.rio.bounds(), densify_pts=21
    )
    shape = reference_raster.rio.shape
    transform = reference_raster.rio.transform()
    mask = np.zeros(shape, dtype=bool)
    n_features = 0
    with pyogrio.open_arrow(
        polygons_path, bbox=bbox, columns=[], use_pyarrow=True, batch_size=batch_size
    ) as (meta, reader):
        for batch in reader:
            wkb = batch.column(meta["geometry_name"] or "wkb_geometry")
            geometries = shapely.from_wkb(wkb.to_numpy(zero_copy_only=False))
            if not layer_crs.equals(raster_crs):
                geometries = gpd.GeoSeries(geometries, crs=layer_crs).to_crs(raster_crs)
            n_features += len(geometries)
            mask |= geometry_mask(
                geometries, out_shape=shape, transform=transform, invert=True
            )
            del geometries
    print(f"Protected areas intersecting the reference raster: {n_features}")
    return mask


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
    to OUTPUT_PATH; resampling it with averaging yields the protected fraction
    of a pixel. SHAPES_PATH is accepted for interface compatibility.
    """
    reference_raster = rxr.open_rasterio(reference_raster_path)

    # FIXME: read the right layer(s) and deal with both poly and point layers
    mask = rasterise_polygons(protected_area_path, reference_raster)
    protected_raster = xr.zeros_like(reference_raster, dtype=np.uint8)
    protected_raster.data[0] = mask
    protected_raster.rio.write_nodata(None, inplace=True)
    protected_raster.rio.to_raster(output_path, driver="GTiff", compress="LZW")


if __name__ == "__main__":
    clip_and_rasterise_polys()
