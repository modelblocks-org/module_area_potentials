"""This script plots a TIF file to PNG format."""

import rioxarray as rxr
from script_utils import plot_all_dataset_variables


def tif_to_png(tif_file_in, png_file_out):
    """Convert a TIF file to PNG format."""
    ds = rxr.open_rasterio(tif_file_in, mask_and_scale=True).to_dataset(
        name=tif_file_in
    )
    plot_all_dataset_variables(
        ds, ncols=2, savefig=png_file_out, categorical_vars=["regions"]
    )


if __name__ == "__main__":
    tif_to_png(snakemake.input[0], snakemake.output[0])
