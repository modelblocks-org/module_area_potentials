import warnings

import geopandas as gpd
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


def utm_buffer(geom, buffer_distance_m=10000, source_crs="EPSG:4326"):
    """Project a geom to UTM, buffer it, then re-project to its source CRS.

    Args:
        geom (shapely.geometry): The geometry to buffer, in the given source_crs.
        buffer_distance_m (int): The buffer distance in meters (default is 10,000 m).
        source_crs (str): The source CRS of the geometry (default is "EPSG:4326").

    Returns:
        shapely.geometry: The buffered geometry in its original CRS.

    """
    try:
        centroid = geom.centroid
        lon, lat = centroid.x, centroid.y
        local_crs = get_utm_crs_from_lonlat(lon, lat)

        # Project to local UTM CRS
        gdf_single = gpd.GeoDataFrame(geometry=[geom], crs=source_crs)
        gdf_utm = gdf_single.to_crs(local_crs)

        # Buffer in meters
        gdf_utm["geometry"] = gdf_utm.buffer(buffer_distance_m)

        # Reproject back to WGS84
        gdf_buffered = gdf_utm.to_crs(source_crs)
        return gdf_buffered.iloc[0].geometry

    except Exception as e:
        warnings.warn(f"Failed to buffer geometry: {e}")
        return None


def apply_utm_buffer(gdf, buffer_distance_m=10000):
    """Apply a UTM-based buffer to a GeoDataFrame with an arbitrary CRS.

    The buffering will be performed row-by-row using the most appropriate UTM zone for
    each geometry's centroid.

    Args:
        gdf (geopandas.GeoDataFrame): The GeoDataFrame containing geometries to buffer.
        buffer_distance_m (int): The buffer distance in meters (default is 10,000 m).

    Returns:
        geopandas.GeoDataFrame: A new GeoDataFrame with buffered geometries.

    """
    source_crs = gdf.crs
    gdf_buffered = gdf.copy()
    gdf_buffered["geometry"] = gdf_buffered["geometry"].apply(
        lambda geom: utm_buffer(geom, buffer_distance_m, source_crs)
    )
    return gdf_buffered
