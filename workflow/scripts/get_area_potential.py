import click
import rioxarray as rxr
import geopandas as gpd


@click.command()
@click.argument("masked_path", type=str)
@click.argument("pixel_area_path", type=str)
@click.argument("technical_mask", type=int)
@click.argument("protected_area_path", type=str)
@click.argument("shapes_path", type=str)
@click.argument("output_path", type=str)
def get_area_potential(
    masked_path,
    pixel_area_path,
    technical_mask,
    protected_area_path,
    shapes_path,
    output_path,
):
    ds_masked = rxr.open_rasterio(masked_path)

    # apply weights
    suitable_land_cover_types = []
    for type, value in technical_mask["land_cover"].items():
        if value == 0:
            continue
        suitable_land_cover_types.appends()
        ds_masked[type] = ds_masked[type] * value

    eligible_fraction = (
        ds_masked[suitable_land_cover_types].to_array().sum(dim="variable")
        - ds_masked["slope"]
        + ds_masked["settlement"] * technical_mask["settlement"]["weight"]
    )

    # remove negative values and values greater than 1
    eligible_fraction = eligible_fraction.clip(0, 1)

    # mask out protected area
    protected_areas = gpd.read_file(protected_area_path)
    eligible_fraction = eligible_fraction.rio.clip(
        protected_areas.geometry, protected_areas.crs, invert=True
    )

    # multiply pixel area to get area potential
    # cut with given shape to return raster inside the shape
    pixel_area = rxr.open_rasterio(pixel_area_path)
    shapes = gpd.read_parquet(shapes_path)
    ds_area_potential = eligible_fraction * pixel_area
    ds_area_potential = ds_area_potential.rio.clip(
        shapes.geometry, shapes.crs, invert=False
    )
    ds_area_potential.to_netcdf(output_path)


if __name__ == "__main__":
    get_area_potential()
