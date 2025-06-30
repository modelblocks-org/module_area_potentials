import click
import math
import geopandas as gpd
import rioxarray as rxr
import xarray as xr
import numpy as np
from rasterio.transform import from_bounds
from rasterio.enums import Resampling
import yaml


def create_empty_geospatial_array(
    bounds,
    resolution,
    projection,
):
    """
    Create an empty geospatial array with specified resolution, projection, and bounds.

    Args:
        bounds (tuple): Bounds of the array (minx, miny, maxx, maxy).
        resolution (float): Resolution of the array in degrees (default: 30 arc-seconds).
        projection (str): CRS of the array (default: "EPSG:4326").

    Returns:
        xarray.DataArray: An empty geospatial array.
    """
    # Calculate the number of pixels in x and y directions
    minx, miny, maxx, maxy = bounds
    width = int((maxx - minx) / resolution)  # Number of pixels in x-direction
    height = int((maxy - miny) / resolution)  # Number of pixels in y-direction

    # Create an empty numpy array filled with NaN
    data = np.full((height, width), np.nan, dtype=np.float32)

    # Define the transform (affine transformation) for the array
    transform = from_bounds(*bounds, width=width, height=height)

    # Generate longitude and latitude coordinates
    longitude = np.linspace(minx, maxx, width)
    latitude = np.linspace(maxy, miny, height)

    # Create an xarray.DataArray with the empty data and geospatial metadata
    geospatial_array = xr.DataArray(
        data,
        dims=("y", "x"),  # Define dimensions as y (latitude) and x (longitude)
        coords={
            "y": ("y", latitude, {"units": "degrees_north"}),  # Latitude coordinates
            "x": ("x", longitude, {"units": "degrees_east"}),  # Longitude coordinates
        },
    )

    # Assign CRS and transform to the DataArray
    geospatial_array.rio.write_crs(projection, inplace=True)  # Set the CRS
    geospatial_array.rio.write_transform(
        transform, inplace=True
    )  # Set the affine transform

    return geospatial_array


def _area_of_pixel(pixel_size, center_lat):
    """Calculate km^2 area of a wgs84 square pixel.

    Adapted from: https://gis.stackexchange.com/a/127327/2397

    Parameters:
        pixel_size (float): length of side of pixel in degrees.
        center_lat (float): latitude of the center of the pixel. Note this
            value +/- half the `pixel-size` must not exceed 90/-90 degrees
            latitude or an invalid area will be calculated.

    Returns:
        Area of square pixel of side length `pixel_size` centered at
        `center_lat` in km^2.

    """
    a = 6378137  # meters
    b = 6356752.3142  # meters
    e = math.sqrt(1 - (b / a) ** 2)
    area_list = []
    for f in [center_lat + pixel_size / 2, center_lat - pixel_size / 2]:
        zm = 1 - e * math.sin(math.radians(f))
        zp = 1 + e * math.sin(math.radians(f))
        area_list.append(
            math.pi
            * b**2
            * (math.log(zp / zm) / (2 * e) + math.sin(math.radians(f)) / (zp * zm))
        )
    return pixel_size / 360.0 * (area_list[0] - area_list[1]) / 1e6


def determine_pixel_areas(raster_input, bounds, resolution, output_name):
    """Returns a raster in which the value corresponds to the area in [m2] of the pixel.
    based on T.Troendle determine_pixel_areas (utils.py and technically_eligible_area.py)
    This assumes the data comprises square pixel in WGS84.

    Parameters:
        crs: the coordinate reference system of the data (must be WGS84)
        bounds: an object with attributes left/right/top/bottom given in degrees
        resolution: the scalar resolution (remember: square pixels) given in degrees
    """
    # the following is based on https://gis.stackexchange.com/a/288034/77760
    # and assumes the data to be in EPSG:4326 (WGS84 is similar but with lat,lon instead of lon,lat)
    assert (
        raster_input.rio.crs.to_epsg() == 4326
    ), "masked_rasters does not have the projection EPSG:4326"
    minx, miny, maxx, maxy = bounds
    width = int((maxx - minx) / resolution)  # Number of pixels in x-direction
    height = int((maxy - miny) / resolution)  # Number of pixels in y-direction

    latitudes = np.linspace(
        start=maxy, stop=miny, num=height, endpoint=True, dtype=np.float64
    )
    varea_of_pixel = np.vectorize(lambda lat: _area_of_pixel(resolution, lat))
    pixel_area = varea_of_pixel(latitudes)  # vector
    pixel_area = pixel_area.repeat(width).reshape(height, width).astype(np.float64)
    pixel_area = xr.DataArray(
        pixel_area * 1000**2,  # convert to m^2
        coords=raster_input.coords,
        dims=raster_input.dims,
        name="pixel_area",
    )
    return pixel_area


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("projection", type=str)
@click.argument("resolution", type=str)
@click.argument("suitable_land_cover_types", type=str)
@click.argument("slope_path", type=str)
@click.argument("land_cover_path", type=str)
@click.argument("settlement_path", type=str)
@click.argument("output_path_pixel_area", type=str)
@click.argument("output_path", type=str)
def get_same_shape_and_resolution(
    shapes_path,
    projection,
    resolution,
    suitable_land_cover_types,
    slope_path,
    land_cover_path,
    settlement_path,
    output_path_pixel_area,
    output_path,
):
    """
    Resample and crop the raster_input
    to have the same bounds, projection, and resolution as the reference_raster
    reproject_match ensures all rasters have the same bounds (minlon, minlat, maxlon, maxlat)
    """
    # create reference raster with the same bounds as given shapes
    shapes = gpd.read_parquet(shapes_path)
    reference_raster = create_empty_geospatial_array(
        bounds=shapes.total_bounds,
        projection=projection,
        resolution=resolution,
    )

    pixel_area = determine_pixel_areas(
        reference_raster,
        bounds=shapes.total_bounds,
        projection=projection,
    )
    pixel_area.to_netcdf(output_path_pixel_area)

    # Resamples the raster to a specified resolution and projection as the given sample
    resampled = xr.Dataset()

    # slope in fraction
    ds_slope = rxr.open_dataset(slope_path)
    resampled["slope_too_steep"] = ds_slope.astype(float).rio.reproject_match(
        reference_raster, resampling=Resampling.average
    )

    # land cover in fraction
    ds_land_cover = rxr.open_dataset(land_cover_path)
    suitable_land_cover_types_dict = yaml.safe_load(suitable_land_cover_types)
    for land_type, value in suitable_land_cover_types_dict.items():
        skip = []
        if value == 0:
            skip.append(land_type)  # skip this one
        else:
            resampled[land_type] = ds_land_cover[land_type].rio.reproject_match(
                reference_raster, resampling=Resampling.average
            )

            # TEST if it's necessary to clip again with cutout
            # # Crops the input raster to the specified geographic bounds
            # # from the bounding box of the sample raster
            # resampled[land_type] = tmp_var.rio.clip_box(*shapes.total_bounds)

    print(f"Skip the land cover types not used in this tech: {skip}")

    # settlement in sum of area of built-up surface (m2)
    ds_settlement = rxr.open_rasterio(settlement_path)
    resampled["settlement"] = ds_settlement.rio.reproject_match(
        reference_raster, resampling=Resampling.sum
    )

    resampled.to_netcdf(output_path)


if __name__ == "__main__":
    get_same_shape_and_resolution()
