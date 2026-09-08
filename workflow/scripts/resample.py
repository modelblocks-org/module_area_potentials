"""This script resamples various geospatial datasets to a common shape and resolution."""

import math

import click
import geopandas as gpd
import numpy as np
import rioxarray as rxr
import xarray as xr
import yaml
from rasterio.enums import Resampling
from rasterio.features import rasterize

# LAND COVER
# Original classification categories taken from GlobCover 2009 land cover.
# From Troendle et al. (2019) https://github.com/timtroendle/possibility-for-electricity-autarky


GLOBCOVER_TYPES = {
    11: "POST_FLOODING_CROPLANDS",
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
    160: "CLOSED_TO_OPEN_REGULARLY_FLOODED_FOREST",
    170: "CLOSED_REGULARLY_FLOODED_FOREST",
    180: "CLOSED_TO_OPEN_REGULARLY_FLOODED_GRASSLAND",
    190: "ARTIFICIAL_SURFACES_AND_URBAN_AREAS",
    200: "BARE_AREAS",
    210: "WATER_BODIES",
    220: "PERMANENT_SNOW",
    230: "NO_DATA",
}


def aggregate_land_cover_types(ds_land_cover, land_cover_types):
    """Convert raw GlobCover data to a dataset with suitable land cover types.

    Maps the integer land cover codes to category ids through a lookup table
    in a single vectorised pass, keeping everything in small integer dtypes.
    Codes without a category (not in GLOBCOVER_TYPES) map to the sentinel 0
    and belong to no category.
    """
    suitable_land_cover = xr.Dataset(coords=ds_land_cover.coords)

    data = ds_land_cover.data
    categories = sorted(set(land_cover_types.values()))
    category_ids = {category: i for i, category in enumerate(categories, start=1)}
    lut = np.zeros(max(256, int(data.max()) + 1), dtype=np.uint8)
    for code, name in GLOBCOVER_TYPES.items():
        lut[code] = category_ids[land_cover_types[name]]
    mapped = lut[data]

    # check if each pixel is in the list of suitable land cover types
    for type_ in categories:
        suitable_land_cover[type_] = (
            ds_land_cover.dims,
            (mapped == category_ids[type_]).astype(np.byte),
        )

    return suitable_land_cover


def _area_of_pixel(pixel_size, center_lat):
    """Calculate km^2 area of a wgs84 square pixel.

    Adapted from: https://gis.stackexchange.com/a/127327/2397

    Parameters:
        pixel_size (float): length of side of pixel in degrees.
        center_lat (float or np.ndarray): latitude of the center of the pixel
            (scalar or array). Note this value +/- half the `pixel-size` must
            not exceed 90/-90 degrees latitude or an invalid area will be
            calculated.

    Returns:
        Area of square pixel of side length `pixel_size` centered at
        `center_lat` in km^2.

    """
    a = 6378137  # meters
    b = 6356752.3142  # meters
    e = math.sqrt(1 - (b / a) ** 2)

    def zone_area(latitude):
        sin_lat = np.sin(np.radians(latitude))
        zm = 1 - e * sin_lat
        zp = 1 + e * sin_lat
        return np.pi * b**2 * (np.log(zp / zm) / (2 * e) + sin_lat / (zp * zm))

    center_lat = np.asarray(center_lat)
    upper = zone_area(center_lat + pixel_size / 2)
    lower = zone_area(center_lat - pixel_size / 2)
    return pixel_size / 360.0 * (upper - lower) / 1e6


def determine_pixel_areas(raster_input):
    """Determine area of each pixel.

    Returns a raster in which the value corresponds to the area in [m2] of the pixel.
    based on T.Troendle determine_pixel_areas (utils.py and technically_eligible_area.py)
    This assumes the data comprises square pixel in WGS84.

    Parameters:
        crs: the coordinate reference system of the data (must be WGS84)
    """
    # the following is based on https://gis.stackexchange.com/a/288034/77760
    # and assumes the data to be in EPSG:4326
    assert raster_input.rio.crs.to_epsg() == 4326, (
        "raster_input does not have the projection EPSG:4326"
    )
    resolution = raster_input.rio.resolution()[0]  # resolution in degrees
    pixel_area = _area_of_pixel(resolution, np.asarray(raster_input.y)) * 1000**2  # m^2

    pixel_area_da = xr.DataArray(pixel_area, coords={"y": raster_input.y}, dims="y")
    return pixel_area_da


def _clip_to_bounds(da, bounds, pad_pixels=2):
    """Clip a raster to the given bounds, padded by a few of its own pixels.

    reproject_match onto a target grid within ``bounds`` only needs the source
    pixels overlapping that grid (plus a small halo for average resampling), so
    inputs can be clipped up front. Because rasters are opened lazily, all
    subsequent arithmetic then reads and processes only the needed window
    instead of the full extent.
    """
    xmin, ymin, xmax, ymax = bounds
    pad = pad_pixels * max(abs(resolution) for resolution in da.rio.resolution())
    return da.rio.clip_box(
        minx=xmin - pad, miny=ymin - pad, maxx=xmax + pad, maxy=ymax + pad
    )


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
@click.argument("land_cover_configuration_yaml_string", type=str)
@click.argument("output_path", type=str)
@click.option("--ship-travel-path", type=str)
def resample_inputs(
    shapes_path,
    land_cover_path,
    slope_path,
    settlement_path,
    bathymetry_path,
    protected_area_path,
    land_cover_configuration_yaml_string,
    output_path,
    ship_travel_path,
):
    """Resample various geospatial datasets to a common shape and resolution.

    Results are saved to the specified output path in NetCDF format.
    (Plotting is a separate workflow step, so that downstream rules do not
    wait for it: see nc_to_png.py.)

    """
    shapes = gpd.read_parquet(shapes_path)
    xmin, ymin, xmax, ymax = shapes.total_bounds
    resampled = xr.Dataset()

    ##
    # Land cover
    ##
    ds_land_cover = rxr.open_rasterio(land_cover_path)

    # By subsetting the land cover dataset to the bounding box of the shapes,
    # we ensure that we only work with the relevant area as this is the reference
    # raster used elsewhere
    ds_land_cover = ds_land_cover.rio.clip_box(
        minx=xmin, miny=ymin, maxx=xmax, maxy=ymax
    )
    land_cover_types = yaml.safe_load(land_cover_configuration_yaml_string)
    reference_raster = xr.ones_like(ds_land_cover, dtype=np.byte)
    reference_resolution = ds_land_cover.rio.resolution()
    print(f"Land cover resolution used as reference resolution: {reference_resolution}")
    land_cover = aggregate_land_cover_types(ds_land_cover, land_cover_types)

    for land_type in sorted(list(set(land_cover_types.values()))):
        resampled[f"landcover_{land_type}"] = land_cover[land_type]
    del ds_land_cover, land_cover

    ##
    # Pixel area
    ##

    pixel_area = determine_pixel_areas(resampled).astype(np.float32)
    resampled["pixel_area"] = pixel_area.expand_dims({"x": resampled.x}).transpose(
        "y", "x"
    )
    del pixel_area

    ##
    # Regions
    ##

    shapes_land = shapes[shapes["shape_class"] == "land"].index
    shapes_maritime = shapes[shapes["shape_class"] == "maritime"].index
    print(f"Number of regions in input data: {len(shapes)}")
    print(f"Number of land regions: {len(shapes_land)}")
    print(f"Number of maritime regions: {len(shapes_maritime)}")

    resampled["regions"] = (("y", "x"), _rasterize_regions(shapes, reference_raster))

    mask_land = xr.DataArray(
        np.isin(resampled["regions"], shapes_land),
        dims=resampled["regions"].dims,
        coords=resampled["regions"].coords,
    )
    mask_maritime = xr.DataArray(
        np.isin(resampled["regions"], shapes_maritime),
        dims=resampled["regions"].dims,
        coords=resampled["regions"].coords,
    )
    resampled["regions_land"] = xr.where(mask_land, np.half(1.0), np.half(np.nan))
    resampled["regions_maritime"] = xr.where(
        mask_maritime, np.half(1.0), np.half(np.nan)
    )
    del mask_land, mask_maritime

    # The clipped land cover grid is the target grid: all other inputs are
    # clipped to its bounds before any arithmetic touches them.
    reference_bounds = reference_raster.rio.bounds()

    ##
    # Slope
    ##
    da_slope = rxr.open_rasterio(slope_path, masked=True)
    print(f"Slope resolution: {da_slope.rio.resolution()}")
    da_slope = _clip_to_bounds(da_slope, reference_bounds) / 100
    resampled["slope_deg"] = da_slope.rio.reproject_match(
        reference_raster, resampling=Resampling.average, num_threads=4
    )
    del da_slope

    ##
    # Settlement in sum of area of built-up surface (m2)
    ##
    ds_settlement = rxr.open_rasterio(settlement_path)
    print(f"Settlement resolution: {ds_settlement.rio.resolution()}")
    # Both operands are cast to float32: a float64 operand would promote the
    # division result (and everything downstream) back to float64.
    ds_settlement = _clip_to_bounds(ds_settlement, reference_bounds).astype(np.float32)

    ds_settlement_pixel_area = (
        determine_pixel_areas(ds_settlement)
        .astype(np.float32)
        .expand_dims({"x": ds_settlement.x})
        .transpose("y", "x")
    )

    # Divide built-up surface (m2) by pixel area (m2) to get built-up surface density,
    # then reproject to match the reference raster
    resampled["settlement_share"] = (
        ds_settlement / ds_settlement_pixel_area
    ).rio.reproject_match(
        reference_raster, resampling=Resampling.average, num_threads=4
    )

    resampled["settlement_area"] = (
        resampled["settlement_share"] * resampled["pixel_area"]
    )
    del ds_settlement, ds_settlement_pixel_area

    ##
    # Bathymetry
    ##

    ds_bathymetry = rxr.open_rasterio(bathymetry_path)
    print(f"Bathymetry resolution: {ds_bathymetry.rio.resolution()}")
    # float32 before the NaN-introducing filter: .where() with NaN on integer
    # data would otherwise promote to float64.
    ds_bathymetry = _clip_to_bounds(ds_bathymetry, reference_bounds).astype(np.float32)
    # Only keep values <= 0, i.e., below sea level
    ds_bathymetry = ds_bathymetry.where(ds_bathymetry <= 0, other=np.nan)
    resampled["bathymetry"] = ds_bathymetry.rio.reproject_match(
        reference_raster, resampling=Resampling.average, num_threads=4
    )
    del ds_bathymetry

    ##
    # Protected areas
    ##
    protected_areas = rxr.open_rasterio(protected_area_path)
    protected_areas = _clip_to_bounds(protected_areas, reference_bounds).astype(
        np.float32
    )
    resampled["protected"] = protected_areas.rio.reproject_match(
        reference_raster, resampling=Resampling.average, num_threads=4
    )
    del protected_areas

    ##
    # Global shipping traffic density (AIS position counts per square kilometre)
    ##
    if ship_travel_path:
        ship_travel = rxr.open_rasterio(ship_travel_path, masked=True)
        print(f"Ship travel resolution: {ship_travel.rio.resolution()}")
        # masked=True already yields float32; clip before the warp like the rest
        ship_travel = _clip_to_bounds(ship_travel, reference_bounds)
        resampled["ship_travel"] = ship_travel.rio.reproject_match(
            reference_raster, resampling=Resampling.average, num_threads=4
        )
        del ship_travel

    netcdf4_encoding = {
        var: {"zlib": True, "complevel": 1}
        for var in resampled.data_vars
        if var not in ["spatial_ref", "band"]
    }
    # int8 with a fill value decodes as float32 (1 / NaN). No scale_factor or
    # add_offset: even no-op ones make xarray decode the variable as float64.
    for v in ["regions_land", "regions_maritime"]:
        netcdf4_encoding[v]["dtype"] = "int8"
        netcdf4_encoding[v]["_FillValue"] = -128
    # Continuous variables are float32 end to end; enforce it on disk as well
    # in case an input source arrives as float64.
    for v in [
        "slope_deg",
        "settlement_share",
        "settlement_area",
        "bathymetry",
        "protected",
        "pixel_area",
        "ship_travel",
    ]:
        if v in netcdf4_encoding:
            netcdf4_encoding[v]["dtype"] = "float32"

    # Source rasters carry no-op scale_factor/add_offset attributes that would
    # be written to the file and make every variable decode as float64
    # downstream, doubling the memory of area_potential.py.
    for var in resampled.data_vars:
        for attr in ["scale_factor", "add_offset"]:
            resampled[var].attrs.pop(attr, None)
            resampled[var].encoding.pop(attr, None)

    print("Saving result to output path:", output_path)
    resampled.to_netcdf(output_path, encoding=netcdf4_encoding)


if __name__ == "__main__":
    resample_inputs()
