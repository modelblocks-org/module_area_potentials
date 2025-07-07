import click
import geo
import geopandas as gpd
import matplotlib.pyplot as plt
import rioxarray as rxr
import xarray as xr
import yaml
from rasterio.enums import Resampling


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("bathymetry_path", type=str)
@click.argument("water_depth", type=str)
@click.argument("resampled_input_path", type=str)
@click.argument("weight", type=float)
@click.argument("output_path", type=str)
@click.argument("plot_path", type=str)
def get_area_potential_offshore(
    shapes_path,
    bathymetry_path,
    water_depth,
    resampled_input_path,
    weight,
    output_path,
    plot_path,
):
    """Get area potential for wind offshore technology.

    Steps:
    - Resample bathymetry and land-sea mask to the same bounds and resolution as the reference raster.
    - Mask out to get only bathymetry within water depth range
    - Mask out land areas, buffer 10 km from country shape, inside geo-boundaries
    - Convert to area potenital in m2

    """
    ds_inputs = xr.open_dataset(resampled_input_path, decode_coords="all")
    shapes = gpd.read_parquet(shapes_path)

    # get bathymetry within the water depth range then resample
    water_depth = yaml.safe_load(water_depth)
    ds_bathymetry = rxr.open_rasterio(bathymetry_path)
    masked_bathymetry = (
        (ds_bathymetry < water_depth["max"]) & (ds_bathymetry >= water_depth["min"])
    ).astype(float)

    ds_inputs["bathymetry"] = masked_bathymetry.rio.reproject_match(
        ds_inputs["pixel_area"], resampling=Resampling.average
    )

    # keep bathymetry inside geo boundaries, i.e. within the exclusive economic zone (EEZ)
    eligible_fraction = ds_inputs["bathymetry"].rio.clip(
        shapes.geometry, shapes.crs, invert=False
    )

    # Buffer 10 km from country shape, no wind offshore too close to the coastline
    shapes_land = shapes[shapes["shape_class"] == "land"]
    sea_buffer = geo.apply_utm_buffer(shapes_land, buffer_distance_m=10000).to_crs(
        ds_inputs.rio.crs
    )["geometry"]
    buffer_geo = gpd.GeoDataFrame(geometry=sea_buffer).to_crs(ds_inputs.rio.crs)
    eligible_fraction = eligible_fraction.rio.clip(
        buffer_geo.geometry, buffer_geo.crs, invert=True
    )

    # exclude protected areas
    eligible_fraction = eligible_fraction.where(ds_inputs["protected"] != 1)

    # apply weight, then multiply pixel area to get area potential
    da_area_potential = xr.Dataset(
        {"area_potential": eligible_fraction * weight * ds_inputs["pixel_area"]},
        coords=ds_inputs["pixel_area"].coords,
    )["area_potential"]
    da_area_potential.to_netcdf(output_path)

    plot = da_area_potential.plot()
    plt.savefig(plot_path, bbox_inches="tight")


if __name__ == "__main__":
    get_area_potential_offshore()
