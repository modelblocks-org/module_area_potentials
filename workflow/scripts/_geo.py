"""This module provides functions to buffer geometries using UTM projections."""

import warnings

import utm
from pyproj import CRS


def get_utm_crs_from_lonlat(lon, lat):
    """Return the appropriate UTM CRS based for the given longitude and latitude.

    Args:
        lon (float): Longitude of the point.
        lat (float): Latitude of the point.

    Returns:
        CRS: The UTM CRS corresponding to the given longitude and latitude.

    """
    easting, northing, zone_number, zone_letter = utm.from_latlon(lat, lon)
    is_northern = lat >= 0
    epsg_code = 32600 + zone_number if is_northern else 32700 + zone_number
    return CRS.from_epsg(epsg_code)


def apply_utm_buffer(gdf, buffer_distance_m=10000):
    """Apply a UTM-based buffer to a GeoDataFrame with an arbitrary CRS.

    The most appropriate UTM zone is chosen per geometry from its centroid;
    geometries are then grouped by zone and each group is projected, buffered
    and re-projected in one vectorised operation (instead of constructing a
    single-row GeoDataFrame and two projection pipelines per geometry).
    Geometries that cannot be buffered (e.g. centroid outside the UTM latitude
    range) produce a warning and None, as before.

    Args:
        gdf (geopandas.GeoDataFrame): The GeoDataFrame containing geometries to buffer.
        buffer_distance_m (int): The buffer distance in meters (default is 10,000 m).

    Returns:
        geopandas.GeoDataFrame: A new GeoDataFrame with buffered geometries.

    """
    source_crs = gdf.crs
    gdf_buffered = gdf.copy()

    zone_indices = {}
    for index, geom in gdf_buffered["geometry"].items():
        try:
            centroid = geom.centroid
            local_crs = get_utm_crs_from_lonlat(centroid.x, centroid.y)
        except Exception as e:
            warnings.warn(f"Failed to buffer geometry: {e}")
            gdf_buffered.loc[index, "geometry"] = None
            continue
        zone_indices.setdefault(local_crs, []).append(index)

    for local_crs, indices in zone_indices.items():
        try:
            buffered = (
                gdf_buffered.loc[indices, "geometry"]
                .set_crs(source_crs, allow_override=True)
                .to_crs(local_crs)
                .buffer(buffer_distance_m)
                .to_crs(source_crs)
            )
        except Exception as e:
            warnings.warn(f"Failed to buffer geometry: {e}")
            buffered = None
        gdf_buffered.loc[indices, "geometry"] = buffered

    return gdf_buffered
