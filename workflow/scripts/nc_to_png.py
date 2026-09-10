"""This script plots all variables of a NetCDF file to PNG format."""

import sys

import xarray as xr
from _script_utils import plot_all_dataset_variables


def nc_to_png(nc_file_in, png_file_out):
    """Plot all variables of a NetCDF file on a grid of panels."""
    # `plot_all_dataset_variables` reads one variable at a time, so setting
    # cache=False here ensures that only one layer is in memory at a time.
    with xr.open_dataset(nc_file_in, decode_coords="all", cache=False) as ds:
        plot_all_dataset_variables(ds, ncols=3, savefig=png_file_out)


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)
    nc_to_png(snakemake.input[0], snakemake.output[0])
