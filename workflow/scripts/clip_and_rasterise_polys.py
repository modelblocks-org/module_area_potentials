"""Rasterise protected-area polygons onto the grid of a reference raster."""

import click
import numpy as np
import pyogrio
import pyproj
import rioxarray as rxr
import xarray as xr
from osgeo import gdal, gdal_array, ogr, osr
from rasterio.warp import transform_bounds

gdal.UseExceptions()
ogr.UseExceptions()
osr.UseExceptions()

# Features per Arrow batch read from the vector source; each batch is burned
# and released before the next one is read.
BATCH_SIZE = 500


def rasterise_polygons(polygons_path, reference_raster, batch_size=BATCH_SIZE):
    """Burn the polygons intersecting the reference grid into a boolean mask.

    This function streams the geometry of features intersecting the reference_raster's
    bounds in Arrow batches. It turns each batch into OGR geometries and burns these
    (via GDAL) into a raster that wraps a NumPy mask. By implementing this directly and
    sidestepping rasterio's `rasterize`, memory use and computation time are greatly
    reduced. Polygons in a different CRS are reprojected on the fly.

    """
    raster_crs = pyproj.CRS.from_user_input(reference_raster.rio.crs)
    layer_crs = pyproj.CRS.from_user_input(pyogrio.read_info(polygons_path)["crs"])
    bbox = transform_bounds(
        raster_crs, layer_crs, *reference_raster.rio.bounds(), densify_pts=21
    )

    mask = np.zeros(reference_raster.rio.shape, dtype=np.uint8)
    target = gdal_array.OpenNumPyArray(mask, True)
    target.SetGeoTransform(reference_raster.rio.transform().to_gdal())
    target.SetProjection(raster_crs.to_wkt())

    def srs(crs):
        result = osr.SpatialReference()
        result.ImportFromWkt(crs.to_wkt())
        result.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        return result

    layer_srs, raster_srs = srs(layer_crs), srs(raster_crs)
    reprojection = (
        None
        if layer_crs.equals(raster_crs)
        else osr.CoordinateTransformation(layer_srs, raster_srs)
    )

    n_features = 0
    with pyogrio.open_arrow(
        polygons_path, bbox=bbox, columns=[], use_pyarrow=True, batch_size=batch_size
    ) as (meta, reader):
        for batch in reader:
            wkbs = batch.column(meta["geometry_name"] or "wkb_geometry").to_pylist()
            source = ogr.GetDriverByName("Memory").CreateDataSource("batch")
            layer = source.CreateLayer("batch", raster_srs, ogr.wkbUnknown)
            definition = layer.GetLayerDefn()
            for wkb in wkbs:
                if wkb is None:
                    continue
                geometry = ogr.CreateGeometryFromWkb(wkb)
                if reprojection is not None:
                    geometry.Transform(reprojection)
                feature = ogr.Feature(definition)
                feature.SetGeometry(geometry)
                layer.CreateFeature(feature)
                n_features += 1
            gdal.RasterizeLayer(target, [1], layer, burn_values=[1])
            del layer, source, wkbs
    target.FlushCache()
    del target
    print(f"Protected areas intersecting the reference raster: {n_features}")
    return mask.astype(bool)


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("reference_raster_path", type=str)
@click.argument("protected_area_path", type=str)
@click.argument("output_path", type=str)
def clip_and_rasterise_polys(
    shapes_path, reference_raster_path, protected_area_path, output_path
):
    """Rasterise the polygons in PROTECTED_AREA_PATH onto reference raster grid.

    A 0/1 uint8 raster on the full reference grid (1 = inside a polygon) is saved to
    OUTPUT_PATH. No resampling happens here. Resample.py later warps this
    raster onto the subunit grid with average resampling, which turns the 0/1
    values into the protected fraction of each pixel.
    SHAPES_PATH is accepted for interface compatibility but not used.
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
