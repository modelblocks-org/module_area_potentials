import click
import yaml
import geopandas as gpd
import xarray as xr
import rioxarray as rxr
from rasterio.enums import Resampling
from rasterio.features import rasterize

from resample import create_empty_geospatial_array, determine_pixel_areas


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("projection", type=str)
@click.argument("resolution", type=float)
@click.argument("bathymetry_path", type=str)
@click.argument("water_depth", type=str)
@click.argument("land_sea_mask_path", type=str)
@click.argument("protected_area_path", type=str)
@click.argument("weight", type=float)
@click.argument("output_path", type=str)
def area_potential_wind_offshore(
    shapes_path,
    projection,
    resolution,
    bathymetry_path,
    water_depth,
    land_sea_mask_path,
    protected_area_path,
    weight,
    output_path,
):
    """Get area potential for wind offshore technology.

    Steps:
    - Resample bathymetry and land-sea mask to the same bounds and resolution as the reference raster.
    - Mask out to get only bathymetry within water depth range
    - Mask out land areas, buffer 10 km from country shape, inside geo-boundaries
    - Convert to area potenital in m2

    """
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

    # keep only bathymetry in sea area using land sea mask
    # NOTE: maybe remove this step since we already include EEZ outside buffer 10 km from coastline
    ds_land_sea_mask = rxr.open_rasterio(land_sea_mask_path)
    ds_land_sea_mask = ds_land_sea_mask.rio.reproject_match(
        pixel_area, resampling=Resampling.mode
    )
    resampled["bathymetry"] = resampled["bathymetry"].where(
        ds_land_sea_mask == 1, other=0
    )

    print(f"Resampled bathymetry and land sea mask: {resampled.dims}, {resampled}")

    # keep bathymetry inside geo boundaries, i.e. within the exclusive economic zone (EEZ)
    eligible_fraction = resampled["bathymetry"].rio.clip(
        shapes.geometry, shapes.crs, invert=False
    )

    # Buffer 10 km from country shape, no wind offshore too close to the coastline
    # Project to a metric CRS equal area EPSG:6933 for buffering
    # Note: a UTM zone specific would be more accurate (e.g., UTM or EPSG:32648) but it varies by country
    shapes_land = shapes[shapes["shape_class"] == "land"]
    sea_buffer = shapes_land.to_crs(epsg=6933).buffer(10_000)  # 10 km buffer outward
    buffer_geo = gpd.GeoDataFrame(geometry=sea_buffer).to_crs(pixel_area.rio.crs)
    eligible_fraction = eligible_fraction.rio.clip(
        buffer_geo.geometry, buffer_geo.crs, invert=True
    )

    # # mask out protected area
    # # FIXME: read the right layer(s) and deal with both poly and point layers
    # protected_areas = gpd.read_file(protected_area_path)
    # # files = list(path_protected_area.glob("*_shp_?/*_shp-polygons.shp"))
    # # gdfs = (gpd.read_file(file) for file in files)  # generator
    # # protected_areas = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))

    # eligible_fraction = eligible_fraction.rio.clip(
    #     protected_areas.geometry, protected_areas.crs, invert=True
    # )

    # apply weight, then multiply pixel area to get area potential
    ds_area_potential = xr.Dataset(
        {"wind_offshore": eligible_fraction * weight * resampled["pixel_area"]},
        coords=resampled["pixel_area"].coords,
    )
    ds_area_potential.to_netcdf(output_path)


if __name__ == "__main__":
    area_potential_wind_offshore()
