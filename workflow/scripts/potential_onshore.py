import click
import geopandas as gpd
import matplotlib.pyplot as plt
import xarray as xr
import yaml


@click.command()
@click.argument("masked_path", type=str)
@click.argument("technical_mask", type=str)
@click.argument("shapes_path", type=str)
@click.argument("output_path", type=str)
@click.argument("plot_path", type=str)
def get_area_potential_onshore(
    masked_path,
    technical_mask,
    shapes_path,
    output_path,
    plot_path,
):
    ds_masked = xr.open_dataset(masked_path)
    technical_mask = yaml.safe_load(technical_mask)

    # apply weights
    suitable_land_cover_types = []
    for type, value in technical_mask["land_cover"].items():
        if value == 0:
            continue
        key = f"landcover_{type}"
        suitable_land_cover_types.append(key)
        ds_masked[key] = ds_masked[key] * value

    eligible_fraction = (
        ds_masked[suitable_land_cover_types].to_array().sum(dim="variable")
        - ds_masked["slope_too_steep"]
        + ds_masked["settlement"] * technical_mask["settlement"]["weight"]
    )

    eligible_fraction = eligible_fraction.where(ds_masked["protected"] != 1)

    eligible_fraction.rio.write_crs("EPSG:4326", inplace=True)

    # remove negative values and values greater than 1
    eligible_fraction = eligible_fraction.clip(0, 1)

    # multiply pixel area to get area potential
    # cut with given shape to return raster inside the shape
    shapes = gpd.read_parquet(shapes_path)
    ds_area_potential = eligible_fraction * ds_masked["pixel_area"]
    ds_area_potential = ds_area_potential.rio.clip(
        shapes.geometry, shapes.crs, invert=False
    )
    ds_area_potential.to_netcdf(output_path)

    plot = ds_area_potential.plot()
    plt.savefig(plot_path, bbox_inches="tight")


if __name__ == "__main__":
    get_area_potential_onshore()
