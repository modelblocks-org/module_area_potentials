import geopandas as gpd
import pandas as pd
import xarray as xr


def report(shapes, resampled_path, area_potentials, csv_path, html_path):
    shapes = gpd.read_parquet(shapes)
    ds_inputs = xr.open_dataset(resampled_path, decode_coords="all")

    for area_potential in area_potentials:
        da = xr.open_dataset(area_potential)
        ds_inputs[area_potential] = da["area_potential"]

    ds_inputs = ds_inputs.squeeze().drop_vars("band")

    dataframes = []
    for area_potential in area_potentials:
        dataframes.append(
            ds_inputs[area_potential].groupby(ds_inputs["regions"]).sum().to_pandas()
        )

    df = pd.concat(dataframes, axis=1)
    df.insert(0, "parent_name", shapes["parent_name"])
    df.insert(0, "shape_class", shapes["shape_class"])
    df.insert(0, "country_id", shapes["country_id"])
    df.insert(0, "shape_id", shapes["shape_id"])

    df.to_csv(csv_path)

    sums = df.sum(numeric_only=True)
    sums.name = "Total"
    df = pd.concat([df, sums.to_frame().T])

    df.to_html(html_path)


if __name__ == "__main__":
    report(
        snakemake.input.shapes,
        snakemake.input.resampled_path,
        snakemake.input.area_potentials,
        snakemake.output.csv,
        snakemake.output.html,
    )
