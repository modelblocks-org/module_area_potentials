import click
import geo
import geopandas as gpd
import matplotlib.pyplot as plt
import rioxarray as rxr
import xarray as xr
import yaml
from rasterio.enums import Resampling
from resample import create_empty_geospatial_array, determine_pixel_areas


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("projection", type=str)
@click.argument("resolution", type=float)
@click.argument("bathymetry_path", type=str)
@click.argument("water_depth", type=str)
@click.argument("resampled_input_path", type=str)
@click.argument("weight", type=float)
@click.argument("output_path", type=str)
@click.argument("plot_path", type=str)
def get_area_potential_offshore(
    shapes_path,
    projection,
    resolution,
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
    ds_inputs = xr.open_dataset(resampled_input_path)

    # resample to the same bounds and resolution as the reference raster
    # create reference raster with the same bounds as given shapes
    shapes = gpd.read_parquet(shapes_path)
    reference_raster = create_empty_geospatial_array(
        bounds=shapes.total_bounds,
        projection=projection,
        resolution=resolution,
    )
    resampled = xr.Dataset()

    pixel_area = determine_pixel_areas(
        reference_raster,
        bounds=shapes.total_bounds,
        resolution=resolution,
    )
    print(f"Pixel area: {pixel_area.dims}, {pixel_area}")
    resampled["pixel_area"] = pixel_area

    # get bathymetry within the water depth range then resample
    water_depth = yaml.safe_load(water_depth)
    ds_bathymetry = rxr.open_rasterio(bathymetry_path)
    masked_bathymetry = (
        (ds_bathymetry < water_depth["max"]) & (ds_bathymetry >= water_depth["min"])
    ).astype(float)

    resampled["bathymetry"] = masked_bathymetry.rio.reproject_match(
        reference_raster, resampling=Resampling.average
    )

    print(f"Resampled bathymetry and land sea mask: {resampled.dims}, {resampled}")

    # keep bathymetry inside geo boundaries, i.e. within the exclusive economic zone (EEZ)
    eligible_fraction = resampled["bathymetry"].rio.clip(
        shapes.geometry, shapes.crs, invert=False
    )

    # Buffer 10 km from country shape, no wind offshore too close to the coastline
    shapes_land = shapes[shapes["shape_class"] == "land"]
    sea_buffer = geo.apply_utm_buffer(shapes_land, buffer_distance_m=10000).to_crs(
        pixel_area.rio.crs
    )["geometry"]
    buffer_geo = gpd.GeoDataFrame(geometry=sea_buffer).to_crs(pixel_area.rio.crs)
    eligible_fraction = eligible_fraction.rio.clip(
        buffer_geo.geometry, buffer_geo.crs, invert=True
    )

    # exclude protected areas
    eligible_fraction = eligible_fraction.where(ds_inputs["protected"] != 1)

    # apply weight, then multiply pixel area to get area potential
    da_area_potential = xr.Dataset(
        {"data": eligible_fraction * weight * resampled["pixel_area"]},
        coords=resampled["pixel_area"].coords,
    )["data"]
    da_area_potential.to_netcdf(output_path)

    plot = da_area_potential.plot()
    plt.savefig(plot_path, bbox_inches="tight")


if __name__ == "__main__":
    get_area_potential_offshore()
