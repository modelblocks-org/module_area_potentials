"""Subset to a bounding box and rasterise polygons."""

import click
import geopandas as gpd
import rioxarray as rxr


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("reference_raster_path", type=str)
@click.argument("protected_area_path", type=str)
@click.argument("output_path", type=str)
def clip_and_rasterise_polys(
    shapes_path, reference_raster_path, protected_area_path, output_path
):
    """Clip the polygons in SHAPES_PATH to the bounding box of the reference raster, and save the clipped polygons as a raster to OUTPUT_PATH."""
    shapes = gpd.read_parquet(shapes_path)
    reference_raster = rxr.open_rasterio(reference_raster_path)

    # FIXME: read the right layer(s) and deal with both poly and point layers
    xmin, ymin, xmax, ymax = shapes.total_bounds
    protected_areas = gpd.read_file(protected_area_path)
    print(f"Protected areas: {len(protected_areas)}")
    protected_areas = protected_areas.cx[xmin:xmax, ymin:ymax]
    print(f"Protected areas after applying total_bounds: {len(protected_areas)}")

    protected_raster = reference_raster.rio.clip(
        protected_areas.geometry, protected_areas.crs
    )
    protected_raster.rio.to_raster(output_path, driver="GTiff", compress="LZW")


if __name__ == "__main__":
    clip_and_rasterise_polys()
