import click
import rioxarray as rxr
import xarray as xr
import numpy as np


# LAND COVER
# Original classification categories taken from GlobCover 2009 land cover.
# From Troendle et al. (2019) https://github.com/timtroendle/possibility-for-electricity-autarky
# suitable land cover types are defined in config.yaml, as 1, other types are 0


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


@click.command()
@click.argument("land_cover_path", type=str)
@click.argument("suitable_land_cover_types", type=int)
@click.argument("output_path", type=str)
def get_suitable_land_cover_type(
    land_cover_path, suitable_land_cover_types, output_path
):
    ds_land_cover = rxr.open_rasterio(land_cover_path)
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
        suitable_land_cover.to_netcdf(output_path)


if __name__ == "__main__":
    get_suitable_land_cover_type()
