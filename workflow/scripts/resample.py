import math

import click
import geopandas as gpd
import numpy as np
import rioxarray as rxr
import script_utils
import xarray as xr
from rasterio.enums import Resampling
from rasterio.features import rasterize

# LAND COVER
# Original classification categories taken from GlobCover 2009 land cover.
# From Troendle et al. (2019) https://github.com/timtroendle/possibility-for-electricity-autarky


GlobCover = {
    11: "POST_FLOODING",
    14: "RAINFED_CROPLANDS",
    20: "MOSAIC_CROPLAND",
    30: "MOSAIC_VEGETATION",
    40: "CLOSED_TO_OPEN_BROADLEAVED_FOREST",
    50: "CLOSED_BROADLEAVED_FOREST",
    60: "OPEN_BROADLEAVED_FOREST",
    70: "CLOSED_NEEDLELEAVED_FOREST",
    90: "OPEN_NEEDLELEAVED_FOREST",
    100: "CLOSED_TO_OPEN_MIXED_FOREST",
    110: "MOSAIC_FOREST",
    120: "MOSAIC_GRASSLAND",
    130: "CLOSED_TO_OPEN_SHRUBLAND",
    140: "CLOSED_TO_OPEN_HERBS",
    150: "SPARSE_VEGETATION",
    160: "CLOSED_TO_OPEN_REGULARLY_FLOODED_FOREST",  # doesn't exist in Europe
    170: "CLOSED_REGULARLY_FLOODED_FOREST",  # doesn't exist in Europe
    180: "CLOSED_TO_OPEN_REGULARLY_FLOODED_GRASSLAND",  # roughly 2.3% of land in Europe
    190: "ARTIFICAL_SURFACES_AND_URBAN_AREAS",
    200: "BARE_AREAS",
    210: "WATER_BODIES",
    220: "PERMANENT_SNOW",
    230: "NO_DATA",
}

CoverType = {
    "POST_FLOODING": "FARM",
    "RAINFED_CROPLANDS": "FARM",
    "MOSAIC_CROPLAND": "FARM",
    "MOSAIC_VEGETATION": "FARM",
    "CLOSED_TO_OPEN_BROADLEAVED_FOREST": "FOREST",
    "CLOSED_BROADLEAVED_FOREST": "FOREST",
    "OPEN_BROADLEAVED_FOREST": "FOREST",
    "CLOSED_NEEDLELEAVED_FOREST": "FOREST",
    "OPEN_NEEDLELEAVED_FOREST": "FOREST",
    "CLOSED_TO_OPEN_MIXED_FOREST": "FOREST",
    "MOSAIC_FOREST": "FOREST",
    "CLOSED_TO_OPEN_REGULARLY_FLOODED_FOREST": "FOREST",
    "CLOSED_REGULARLY_FLOODED_FOREST": "FOREST",
    "MOSAIC_GRASSLAND": "OTHER",  # vegetation
    "CLOSED_TO_OPEN_SHRUBLAND": "OTHER",  # vegetation
    "CLOSED_TO_OPEN_HERBS": "OTHER",  # vegetation
    "SPARSE_VEGETATION": "OTHER",  # vegetation
    "CLOSED_TO_OPEN_REGULARLY_FLOODED_GRASSLAND": "OTHER",  # vegetation
    "BARE_AREAS": "OTHER",
    "ARTIFICAL_SURFACES_AND_URBAN_AREAS": "URBAN",
    "WATER_BODIES": "WATER",
    "PERMANENT_SNOW": "NA",
    "NO_DATA": "NA",
}


def get_suitable_land_cover_type(ds_land_cover, suitable_land_cover_types):
    suitable_land_cover = xr.Dataset(coords=ds_land_cover.coords)

    # convert the input value to land cover type of interest
    for value in np.unique(ds_land_cover.data):
        if value in GlobCover:
            ds_land_cover = ds_land_cover.where(
                ds_land_cover != value, other=CoverType[GlobCover[value]], drop=False
            )

    # check if each pixel is in the list of suitable land cover types
    for type in suitable_land_cover_types:
        suitable_land_cover[type] = (ds_land_cover == type).astype(float)

    return suitable_land_cover


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


def determine_pixel_areas(raster_input):
    """Determine area of each pixel.

    Returns a raster in which the value corresponds to the area in [m2] of the pixel.
    based on T.Troendle determine_pixel_areas (utils.py and technically_eligible_area.py)
    This assumes the data comprises square pixel in WGS84.

    Parameters:
        crs: the coordinate reference system of the data (must be WGS84)
    """
    # the following is based on https://gis.stackexchange.com/a/288034/77760
    # and assumes the data to be in EPSG:4326 (WGS84 is similar but with lat,lon instead of lon,lat)
    assert (
        raster_input.rio.crs.to_epsg() == 4326
    ), "raster_input does not have the projection EPSG:4326"
    resolution = raster_input.rio.resolution()[0]  # resolution in degrees
    varea_of_pixel = np.vectorize(lambda lat: _area_of_pixel(resolution, lat))
    pixel_area = varea_of_pixel(raster_input.y) * 1000**2  # convert to m^2

    pixel_area_da = xr.DataArray(pixel_area, coords={"y": raster_input.y}, dims="y")
    return pixel_area_da


def _rasterize_regions(shapes, reference_raster):
    regions = [(geom, idx) for idx, geom in zip(shapes.index, shapes.geometry)]
    return rasterize(
        shapes=regions,
        out_shape=reference_raster.rio.shape,
        transform=reference_raster.rio.transform(),
        fill=np.nan,
        dtype=np.float32,
    )


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("land_cover_path", type=str)
@click.argument("slope_path", type=str)
@click.argument("settlement_path", type=str)
@click.argument("bathymetry_path", type=str)
@click.argument("protected_area_path", type=str)
@click.argument("output_path", type=str)
@click.argument("plot_path", type=str)
def get_same_shape_and_resolution(
    shapes_path,
    land_cover_path,
    slope_path,
    settlement_path,
    bathymetry_path,
    protected_area_path,
    output_path,
    plot_path,
):
    shapes = gpd.read_parquet(shapes_path)
    print(f"Number of shapes in input data: {len(shapes)}")

    ##
    # Land cover
    ##
    suitable_land_cover_types = sorted(list(set(CoverType.values())))
    ds_land_cover = rxr.open_rasterio(land_cover_path)
    reference_raster = xr.ones_like(ds_land_cover)
    reference_resolution = ds_land_cover.rio.resolution()
    print(f"Land cover resolution: {reference_resolution}")
    land_cover = get_suitable_land_cover_type(ds_land_cover, suitable_land_cover_types)

    resampled = xr.Dataset()

    for land_type in suitable_land_cover_types:
        resampled[f"landcover_{land_type}"] = land_cover[land_type].rio.reproject_match(
            reference_raster, resampling=Resampling.average
        )

    # Drop the "band" dimension
    resampled = resampled.squeeze().drop_vars("band")

    ##
    # Pixel area
    ##

    pixel_area = determine_pixel_areas(resampled)
    resampled["pixel_area"] = pixel_area.expand_dims({"x": resampled.x}).transpose(
        "y", "x"
    )

    ##
    # Regions
    ##


    resampled["regions"] = (
        ("y", "x"),
        _rasterize_regions(shapes, reference_raster),
    )

    ##
    # Slope
    ##
    da_slope = rxr.open_rasterio(slope_path, masked=True) / 100
    print(f"Slope resolution: {da_slope.rio.resolution()}")
    resampled["slope"] = da_slope.astype(float).rio.reproject_match(
        reference_raster, resampling=Resampling.average
    )

    ##
    # Settlement in sum of area of built-up surface (m2)
    ##
    ds_settlement = rxr.open_rasterio(settlement_path)
    print(f"Settlement resolution: {ds_settlement.rio.resolution()}")
    ds_settlement.rio.write_crs("EPSG:4326", inplace=True)
    resampled["settlement"] = ds_settlement.rio.reproject_match(
        reference_raster, resampling=Resampling.sum
    )
    # get fraction of settlement (built-up surface) compared to pixel area, both in m2
    resampled["settlement"] = resampled["settlement"] / resampled["pixel_area"]

    ##
    # Bathymetry
    ##

    ds_bathymetry = rxr.open_rasterio(bathymetry_path)
    print(f"Bathymetry resolution: {ds_bathymetry.rio.resolution()}")
    resampled["bathymetry"] = ds_bathymetry.rio.reproject_match(
        reference_raster, resampling=Resampling.average
    )

    ##
    # Protected areas
    ##
    # FIXME: read the right layer(s) and deal with both poly and point layers
    xmin, ymin, xmax, ymax = shapes.total_bounds
    protected_areas = gpd.read_file(protected_area_path)
    print(f"Protected areas: {len(protected_areas)}")
    protected_areas = protected_areas.cx[xmin:xmax, ymin:ymax]
    print(f"Protected areas after applying total_bounds: {len(protected_areas)}")

    resampled["protected"] = reference_raster.rio.clip(
        protected_areas.geometry, protected_areas.crs
    )
    resampled["protected"] = resampled["protected"].fillna(0)

    resampled.to_netcdf(output_path)

    script_utils.plot_all_dataset_variables(resampled, savefig=plot_path)


if __name__ == "__main__":
    get_same_shape_and_resolution()
