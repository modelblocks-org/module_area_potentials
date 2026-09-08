"""This script plots a TIF file to PNG format."""

import math
import sys

import numpy as np
import rasterio
import rioxarray  # noqa: F401  # activates the .rio accessor
import xarray as xr
from _script_utils import plot_all_dataset_variables
from rasterio.enums import Resampling

# Matches the cap in plot_all_dataset_variables: a 6x4 inch panel at 300 dpi
# cannot show more than ~1.2M pixels, so 2M source pixels are lossless.
MAX_PIXELS = 2_000_000


def read_decimated(tif_file, max_pixels=MAX_PIXELS):
    """Read a single-band raster at a resolution of at most ``max_pixels``.

    Reading through GDAL's decimated I/O averages blocks on the fly, so the
    full-resolution raster is never held in memory (plotting a country-group
    mosaic previously needed several GB just to coarsen it).
    """
    # A small block cache: GDAL would otherwise keep decoded blocks of the
    # full-resolution raster around (default cache is 5% of RAM).
    with rasterio.Env(GDAL_CACHEMAX=256), rasterio.open(tif_file) as src:
        factor = max(1, math.ceil(math.sqrt(src.width * src.height / max_pixels)))
        height, width = math.ceil(src.height / factor), math.ceil(src.width / factor)
        data = src.read(
            1, out_shape=(height, width), resampling=Resampling.average, masked=True
        )
        transform = src.transform * src.transform.scale(
            src.width / width, src.height / height
        )
        crs = src.crs
    x = transform.c + transform.a * (np.arange(width) + 0.5)
    y = transform.f + transform.e * (np.arange(height) + 0.5)
    da = xr.DataArray(
        data.filled(np.nan).astype(np.float32), dims=("y", "x"), coords={"y": y, "x": x}
    )
    return da.rio.write_crs(crs, inplace=True)


def tif_to_png(tif_file_in, png_file_out):
    """Convert a TIF file to PNG format."""
    ds = read_decimated(tif_file_in).to_dataset(name=tif_file_in)
    plot_all_dataset_variables(
        ds, ncols=2, savefig=png_file_out, categorical_vars=["regions"]
    )


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)
    tif_to_png(snakemake.input[0], snakemake.output[0])
