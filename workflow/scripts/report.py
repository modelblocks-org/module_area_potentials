import geopandas as gpd
import pandas as pd
import rioxarray as rxr
import xarray as xr


def report(shapes, resampled_path, area_potentials, csv_path, html_path):
    shapes = gpd.read_parquet(shapes)
    ds_inputs = xr.open_dataset(resampled_path, decode_coords="all")
    # FIXME: this is a workaround for the CRS not being set correctly; not sure why
    ds_inputs.rio.write_crs(ds_inputs.spatial_ref.attrs["crs_wkt"], inplace=True)

    # Collect the area potentials from the input files
    for area_potential in area_potentials:
        ds_inputs[area_potential] = rxr.open_rasterio(area_potential)
    ds_inputs = ds_inputs.squeeze().drop_vars(["band", "spatial_ref"])

    # Group the area potentials by regions, sum them up, and collect the resulting Series
    # into a DataFrame, where each column corresponds to a technology's area potential,
    # and the index corresponds to the regions.
    dataframes = []
    for area_potential in area_potentials:
        dataframes.append(
            ds_inputs[area_potential].groupby(ds_inputs["regions"]).sum().to_pandas()
        )
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

    df.to_html(html_path, float_format=lambda x: f"{x/1e6:.2f}")


if __name__ == "__main__":
    report(
        snakemake.input.shapes,
        snakemake.input.resampled_path,
        snakemake.input.area_potentials,
        snakemake.output.csv,
        snakemake.output.html,
    )
