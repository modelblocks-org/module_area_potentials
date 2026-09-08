"""This script generates a report summarizing area potentials for different technologies."""

import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.windows
from rasterio.features import rasterize

STRIP_ROWS = 1024


def report(shapes, area_potentials, csv_path, html_path):
    """Generate a report summarizing area potentials for different technologies."""
    shapes = gpd.read_parquet(shapes)

    with rasterio.open(area_potentials[0]) as src:
        reference_shape = (src.height, src.width)
        reference_transform = src.transform
        windows = [
            rasterio.windows.Window(
                0, row, src.width, min(STRIP_ROWS, src.height - row)
            )
            for row in range(0, src.height, STRIP_ROWS)
        ]

    # Sums (and pixel counts) per region are accumulated strip by strip: the
    # region index is burned per strip and each technology mosaic is read per
    # strip, so memory stays bounded by a strip instead of several full-size
    # copies of a country-group mosaic. (Rasters small enough for one strip
    # give bit-identical sums to a whole-raster aggregation.)
    sums = {path: np.zeros(len(shapes)) for path in area_potentials}
    pixel_counts = np.zeros(len(shapes), dtype=np.int64)
    sources = [rasterio.open(path) for path in area_potentials]
    try:
        for src in sources:
            # All technology mosaics must lie on the same grid, otherwise the
            # region index would silently aggregate the wrong pixels.
            assert (src.height, src.width) == reference_shape, (
                f"Raster shape of {src.name} does not match {area_potentials[0]}"
            )
            assert src.transform == reference_transform, (
                f"Raster transform of {src.name} does not match {area_potentials[0]}"
            )
        print(
            f"Aggregating {len(area_potentials)} rasters over {len(windows)} windows..."
        )
        for window in windows:
            # Burn each shape's row position (-1 = no region) for this window
            region_ids = rasterize(
                zip(shapes.geometry, range(len(shapes))),
                out_shape=(window.height, window.width),
                transform=rasterio.windows.transform(window, reference_transform),
                fill=-1,
                dtype=np.int32,
            ).ravel()
            valid = region_ids >= 0
            if not valid.any():
                continue
            region_ids = region_ids[valid]
            pixel_counts += np.bincount(region_ids, minlength=len(shapes))
            for path, src in zip(area_potentials, sources):
                values = src.read(1, window=window, masked=True).ravel()[valid]
                # nodata/NaN pixels contribute nothing (as the groupby-sum did)
                weights = np.nan_to_num(values.filled(np.nan))
                sums[path] += np.bincount(
                    region_ids, weights=weights, minlength=len(shapes)
                )
    finally:
        for src in sources:
            src.close()
    columns = sums

    # Regions owning no pixel were never part of the groupby-based report;
    # keep them out.
    df = pd.DataFrame(columns, index=shapes.index.astype(float))
    df = df[pixel_counts > 0].sort_index()
    df.index.name = "group"

    # Add metadata columns from shapes in front of the data columns
    df.insert(0, "parent_name", shapes["parent_name"])
    df.insert(0, "shape_class", shapes["shape_class"])
    df.insert(0, "country_id", shapes["country_id"])
    df.insert(0, "shape_id", shapes["shape_id"])

    df.to_csv(csv_path)

    # After saving the CSV and before saving a HTML file,
    # we add a "total" row for the numeric columns
    sums = df.sum(numeric_only=True)
    sums.name = "Total"
    df = pd.concat([df, sums.to_frame().T])

    df.to_html(html_path, float_format=lambda x: f"{x / 1e6:.2f}")


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)
    report(
        snakemake.input.shapes,
        snakemake.input.area_potentials,
        snakemake.output.csv,
        snakemake.output.html,
    )
