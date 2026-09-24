"""This script plots a TIF file to PNG format."""

import math
import sys

import numpy as np
import rasterio
import rioxarray  # noqa: F401  # activates the .rio accessor
import xarray as xr
from _plots import plot_all_dataset_variables
from rasterio.enums import Resampling

MAX_PIXELS = 2_000_000  # Matches the cap in plot_all_dataset_variables


def read_decimated(tif_file, max_pixels=MAX_PIXELS):
    """Read a single-band raster with at most ``max_pixels`` pixels in total.

    Reading through GDAL's decimated I/O means that blocks are averaged on the fly.
    Therefore, the full-resolution raster is never held in memory, saving GBs of RAM
    on large plots.

    Returns a float32 ``(y, x)`` DataArray with pixel-centre coordinates and the
    raster's CRS, and NaN where the source has no data.

    """
    # Specify a block cache of 256 MB. GDAL would otherwise keep decoded blocks of the
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
