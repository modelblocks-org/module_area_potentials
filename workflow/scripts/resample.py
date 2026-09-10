"""This script resamples various geospatial datasets to a common shape and resolution."""

import gc
import math

import click
import geopandas as gpd
import numpy as np
import rasterio
import rioxarray as rxr
import xarray as xr
import yaml
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject
from rasterio.windows import Window, from_bounds

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


def land_cover_category_ids(ds_land_cover, land_cover_types):
    """Map GlobCover codes to small category ids in one vectorised pass.

    Returns ``(mapped, category_ids)``:
        `mapped`: a uint8 array shaped like ds_land_cover, holding the `id` of
                  each pixel's category
        `category_ids`: a dict mapping `category` to `id`

    Codes without a category (not in GLOBCOVER_TYPES) map to the sentinel 0
    and belong to no category.

    """
    data = ds_land_cover.data
    categories = sorted(set(land_cover_types.values()))
    category_ids = {category: i for i, category in enumerate(categories, start=1)}
    # Size the table from the dtype rather than data.max(): the latter would
    # load and scan the whole raster just to build a 256-entry table.
    lut = np.zeros(np.iinfo(data.dtype).max + 1, dtype=np.uint8)
    for code, name in GLOBCOVER_TYPES.items():
        lut[code] = category_ids[land_cover_types[name]]
    return lut[data], category_ids


def land_cover_mask(ds_land_cover, mapped, category_id):
    """Return the 0/1 int8 membership mask of one land cover category."""
    return xr.DataArray(
        (mapped == category_id).astype(np.byte),
        dims=ds_land_cover.dims,
        coords=ds_land_cover.coords,
    )


def aggregate_land_cover_types(ds_land_cover, land_cover_types):
    """Turn a GlobCover class raster into a Dataset of per-category membership masks."""
    mapped, category_ids = land_cover_category_ids(ds_land_cover, land_cover_types)
    suitable_land_cover = xr.Dataset(coords=ds_land_cover.coords)
    for type_, category_id in category_ids.items():
        suitable_land_cover[type_] = land_cover_mask(ds_land_cover, mapped, category_id)
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


def _warp_from_file(
    input_raster_path, reference_raster, prepare, num_threads=1, warp_nodata=None
):
    """Warp an input raster from file onto the reference grid with average resampling.

    This function goes through the following procedure:

    - Reads the window of ``input_raster_path`` covering the reference grid (plus a
      two-pixel buffer) in its native dtype.
    - Lets ``prepare(data, nodata, transform)`` turn it into the float32 array to
      warp, and assigns NaN where there is no useful value.
    - Warps the prepared array.

    This process reduces the copies held in memory compared to xarray + reproject_match.

    ``num_threads`` is passed on to GDAL's warp.

    ``warp_nodata`` is the nodata value declared to GDAL. Set it to ``None``, ``"file"``
    for the source file's own, or an explicit value. Declared nodata pixels
    are excluded from the averages; any other NaN turns every target pixel it
    touches into NaN.

    Returns a float32 ``(band, y, x)`` DataArray on the reference grid, with
    the reference CRS written and NaN wherever the warp produced no value.

    """
    with rasterio.open(input_raster_path) as src:
        xmin, ymin, xmax, ymax = reference_raster.rio.bounds()
        pad = 2 * max(abs(res) for res in src.res)
        window = from_bounds(
            xmin - pad, ymin - pad, xmax + pad, ymax + pad, transform=src.transform
        )
        window = window.round_offsets().round_lengths()
        window = window.intersection(Window(0, 0, src.width, src.height))
        data = src.read(1, window=window)
        src_transform = src.window_transform(window)
        src_crs = src.crs
        src_nodata = src.nodata
    data = prepare(data, src_nodata, src_transform)
    assert data.dtype == np.float32
    if isinstance(warp_nodata, str) and warp_nodata == "file":
        warp_nodata = src_nodata
    destination = np.full(reference_raster.rio.shape, np.nan, dtype=np.float32)
    reproject(
        source=data,
        destination=destination,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=warp_nodata,
        dst_transform=reference_raster.rio.transform(),
        dst_crs=reference_raster.rio.crs,
        dst_nodata=np.nan,
        resampling=Resampling.average,
        num_threads=num_threads,
    )
    del data
    warped = xr.DataArray(
        destination[np.newaxis],
        dims=("band", "y", "x"),
        coords={"band": [1], "y": reference_raster.y, "x": reference_raster.x},
    )
    return warped.rio.write_crs(reference_raster.rio.crs, inplace=True)


def _masked_float32(data, nodata, _transform, rows_per_chunk=1024):
    """Native array to float32 with NaN where the source declares nodata.

    Converted in row chunks so that no full-size temporary (e.g. the boolean
    nodata mask) exists next to the input and output arrays.
    """
    out = np.empty(data.shape, dtype=np.float32)
    for start in range(0, data.shape[0], rows_per_chunk):
        rows = slice(start, start + rows_per_chunk)
        out[rows] = data[rows]
        if nodata is not None:
            out[rows][data[rows] == nodata] = np.nan
    return out


class _NetcdfWriter:
    """Write variables to a NetCDF file one at a time.

    Holding every resampled layer in memory before a single ``to_netcdf`` would make
    the peak memory of this script proportional to the *sum* of all outputs
    (several GB for country-sized subunits). Appending variables as soon as
    they are computed bounds it to the largest single layer pipeline instead.
    """

    def __init__(self, path):
        self.path = path
        self.mode = "w"

    def write(self, name, da, dtype=None, fill_value=None):
        encoding = {"zlib": True, "complevel": 1}
        if dtype is not None:
            encoding["dtype"] = dtype
        if fill_value is not None:
            encoding["_FillValue"] = fill_value
        # Source rasters carry no-op scale_factor/add_offset attributes that
        # would be written to the file and make the variable decode as float64
        # downstream, doubling the memory of area_potential.py.
        for attr in ["scale_factor", "add_offset"]:
            da.attrs.pop(attr, None)
            da.encoding.pop(attr, None)
        da.to_dataset(name=name).to_netcdf(
            self.path, mode=self.mode, encoding={name: encoding}
        )
        self.mode = "a"
        # rioxarray caches its accessor on the array and the accessor points
        # back at it, so large buffers are only released by the cyclic GC.
        del da
        gc.collect()


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
@click.option(
    "--num-threads",
    type=int,
    default=1,
    show_default=True,
    help="Threads used by the GDAL warps (set from the rule's threads).",
)
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
    num_threads,
):
    """Resample various geospatial datasets to a common shape and resolution.

    Results are saved to the specified output path in NetCDF format.
    (Plotting is a separate workflow step, so that downstream rules do not
    wait for it: see nc_to_png.py.)

    """
    shapes = gpd.read_parquet(shapes_path)
    xmin, ymin, xmax, ymax = shapes.total_bounds
    writer = _NetcdfWriter(output_path)
    print("Saving results to output path:", output_path)

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

    # Below, we go through the different inputs one by one.
    # The warped inputs come first. The slope warp is the largest single memory
    # allocation of this script, and running it before anything else is
    # resident in memory keeps the peak memory to that one stage.

    ##
    # Slope: GEDTM30 stores degrees * 100 as uint16
    ##
    def prepare_slope(data, nodata, transform):
        out = _masked_float32(data, nodata, transform)
        out /= 100
        return out

    writer.write(
        "slope_deg",
        _warp_from_file(slope_path, reference_raster, prepare_slope, num_threads),
        dtype="float32",
    )

    ##
    # Settlement in sum of area of built-up surface (m2)
    ##

    # One value per row (dims: y); broadcast against x only when written.
    pixel_area = determine_pixel_areas(reference_raster).astype(np.float32)

    def prepare_settlement(data, nodata, transform):
        # Divide built-up surface (m2) by the source pixel area (m2) to get the
        # built-up share; both operands float32 so the result stays float32.
        # Pixel areas depend on latitude only (one value per row).
        assert rasterio.crs.CRS.from_user_input(src_crs).to_epsg() == 4326, (
            "settlement raster does not have the projection EPSG:4326"
        )
        rows = np.arange(data.shape[0])
        centre_lat = transform.f + transform.e * (rows + 0.5)
        pixel_area_m2 = (_area_of_pixel(abs(transform.a), centre_lat) * 1000**2).astype(
            np.float32
        )
        return data.astype(np.float32) / pixel_area_m2[:, np.newaxis]

    with rasterio.open(settlement_path) as src:
        src_crs = src.crs
        print(f"Settlement resolution: {src.res}")
    settlement_share = _warp_from_file(
        settlement_path, reference_raster, prepare_settlement, num_threads
    )
    writer.write("settlement_share", settlement_share, dtype="float32")
    writer.write(
        "settlement_area",
        (settlement_share * pixel_area).transpose(*settlement_share.dims),
        dtype="float32",
    )
    del settlement_share

    ##
    # Bathymetry: only keep values <= 0, i.e., below sea level
    ##
    def prepare_bathymetry(data, nodata, transform):
        out = data.astype(np.float32)
        out[out > 0] = np.nan
        return out

    writer.write(
        "bathymetry",
        _warp_from_file(
            bathymetry_path,
            reference_raster,
            prepare_bathymetry,
            num_threads,
            warp_nodata="file",
        ),
        dtype="float32",
    )

    ##
    # Protected areas (0/1 mask, becomes the protected fraction when averaged)
    ##
    def prepare_protected(data, nodata, transform):
        return data.astype(np.float32)

    writer.write(
        "protected",
        _warp_from_file(
            protected_area_path,
            reference_raster,
            prepare_protected,
            num_threads,
            warp_nodata="file",
        ),
        dtype="float32",
    )

    ##
    # Global shipping traffic density (AIS position counts per square kilometre)
    ##
    if ship_travel_path:
        writer.write(
            "ship_travel",
            _warp_from_file(
                ship_travel_path,
                reference_raster,
                _masked_float32,
                num_threads,
                warp_nodata=np.nan,
            ),
            dtype="float32",
        )

    ##
    # Pixel area
    ##

    writer.write(
        "pixel_area",
        pixel_area.expand_dims({"x": reference_raster.x})
        .transpose("y", "x")
        .rio.write_crs(reference_raster.rio.crs, inplace=True),
        dtype="float32",
    )

    ##
    # Regions
    ##

    shapes_land = shapes[shapes["shape_class"] == "land"].index
    shapes_maritime = shapes[shapes["shape_class"] == "maritime"].index
    print(f"Number of regions in input data: {len(shapes)}")
    print(f"Number of land regions: {len(shapes_land)}")
    print(f"Number of maritime regions: {len(shapes_maritime)}")

    regions = xr.DataArray(
        _rasterize_regions(shapes, reference_raster),
        dims=("y", "x"),
        coords={"y": reference_raster.y, "x": reference_raster.x},
    ).rio.write_crs(reference_raster.rio.crs, inplace=True)
    writer.write("regions", regions)

    # int8 with a fill value decodes as float32 (1 / NaN). No scale_factor or
    # add_offset: even no-op ones make xarray decode the variable as float64.
    for name, index in [
        ("regions_land", shapes_land),
        ("regions_maritime", shapes_maritime),
    ]:
        mask = xr.DataArray(
            np.isin(regions, index), dims=regions.dims, coords=regions.coords
        )
        writer.write(
            name,
            xr.where(mask, np.half(1.0), np.half(np.nan)).rio.write_crs(
                reference_raster.rio.crs, inplace=True
            ),
            dtype="int8",
            fill_value=-128,
        )
        del mask
    del regions

    mapped, category_ids = land_cover_category_ids(ds_land_cover, land_cover_types)
    for land_type, category_id in category_ids.items():
        writer.write(
            f"landcover_{land_type}",
            land_cover_mask(ds_land_cover, mapped, category_id),
        )
    del ds_land_cover, mapped


if __name__ == "__main__":
    resample_inputs()
