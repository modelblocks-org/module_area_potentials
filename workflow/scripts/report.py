"""This script generates a report summarizing area potentials for different technologies."""

import geopandas as gpd
import pandas as pd
import rioxarray as rxr
import xarray as xr
from resample import _rasterize_regions


def report(shapes, area_potentials, csv_path, html_path):
    """Generate a report summarizing area potentials for different technologies."""
    shapes = gpd.read_parquet(shapes)

    print("Generating reference raster and rasterizing regions...")
    reference_raster = rxr.open_rasterio(area_potentials[0])
    regions = xr.DataArray(
        _rasterize_regions(shapes, reference_raster),
        dims=("y", "x"),
        coords={"y": reference_raster.y, "x": reference_raster.x},
    )
    # regions = xr.DataArray(("y", "x"), _rasterize_regions(shapes, reference_raster))
    del reference_raster

    # Collect the area potentials from the input files
    # Group the area potentials by regions, sum them up, and collect the resulting Series
    # into a DataFrame, where each column corresponds to a technology's area potential,
    # and the index corresponds to the regions.
    dataframes = []
    for area_potential_file in area_potentials:
        print(f"Processing area potential file: {area_potential_file}")
        da_area_potential = (
            rxr.open_rasterio(area_potential_file, mask_and_scale=True)
            .squeeze()
            .drop_vars(["band", "spatial_ref"])
        )
        df_ = da_area_potential.groupby(regions).sum().to_pandas()
        df_.name = area_potential_file
        dataframes.append(df_)
        del da_area_potential

    df = pd.concat(dataframes, axis=1)

    # Add metadata columns from shapes in front of the data columns
    df.insert(0, "parent_name", shapes["parent_name"])
    df.insert(0, "shape_class", shapes["shape_class"])
    df.insert(0, "country_id", shapes["country_id"])
    df.insert(0, "shape_id", shapes["shape_id"])

    df.to_csv(csv_path)

    # After saving the CSV and before saving a HTML file,
    # we add a "total" row for the numeric columns
    sums = df.sum(numeric_only=True)
    sums.name = "Total"
    df = pd.concat([df, sums.to_frame().T])

    df.to_html(html_path, float_format=lambda x: f"{x / 1e6:.2f}")


if __name__ == "__main__":
    report(
        snakemake.input.shapes,
        snakemake.input.area_potentials,
        snakemake.output.csv,
        snakemake.output.html,
    )
