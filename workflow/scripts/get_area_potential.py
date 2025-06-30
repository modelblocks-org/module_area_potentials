import click
import geopandas as gpd
import xarray as xr
import yaml


@click.command()
@click.argument("masked_path", type=str)
@click.argument("technical_mask", type=str)
@click.argument("protected_area_path", type=str)
@click.argument("shapes_path", type=str)
@click.argument("output_path", type=str)
def get_area_potential(
    masked_path,
    technical_mask,
    protected_area_path,
    shapes_path,
    output_path,
):
    ds_masked = xr.open_dataset(masked_path)
    technical_mask = yaml.safe_load(technical_mask)

    # apply weights
    suitable_land_cover_types = []
    for type, value in technical_mask["land_cover"].items():
        if value == 0:
            continue
        suitable_land_cover_types.append(type)
        ds_masked[type] = ds_masked[type] * value

    eligible_fraction = (
        ds_masked[suitable_land_cover_types].to_array().sum(dim="variable")
        - ds_masked["slope_too_steep"]
        + ds_masked["settlement"] * technical_mask["settlement"]["weight"]
    )
    eligible_fraction.rio.write_crs("EPSG:4326", inplace=True)

    # remove negative values and values greater than 1
    eligible_fraction = eligible_fraction.clip(0, 1)

    # mask out protected area
    # FIXME: read the right layer(s) and deal with both poly and point layers
    protected_areas = gpd.read_file(protected_area_path)
    eligible_fraction = eligible_fraction.rio.clip(
        protected_areas.geometry, protected_areas.crs, invert=True
    )

    # multiply pixel area to get area potential
    # cut with given shape to return raster inside the shape
    shapes = gpd.read_parquet(shapes_path)
    ds_area_potential = eligible_fraction * ds_masked["pixel_area"]
    ds_area_potential = ds_area_potential.rio.clip(
        shapes.geometry, shapes.crs, invert=False
    )
    ds_area_potential.to_netcdf(output_path)


if __name__ == "__main__":
    get_area_potential()
