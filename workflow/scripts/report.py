"""This script generates a report summarizing area potentials for different technologies."""

import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize


def report(shapes, area_potentials, csv_path, html_path):
    """Generate a report summarizing area potentials for different technologies."""
    shapes = gpd.read_parquet(shapes)

    print("Generating reference raster and rasterizing regions...")
    with rasterio.open(area_potentials[0]) as src:
        reference_shape = (src.height, src.width)
        reference_transform = src.transform

    # Burn each shape's row position once as int32 (-1 = no region): the
    # bincount aggregation below then replaces a full groupby factorisation
    # of the region raster for every technology file.
    region_ids = rasterize(
        zip(shapes.geometry, range(len(shapes))),
        out_shape=reference_shape,
        transform=reference_transform,
        fill=-1,
        dtype=np.int32,
    ).ravel()
    valid = region_ids >= 0
    region_ids = region_ids[valid]
    pixel_counts = np.bincount(region_ids, minlength=len(shapes))

    # Sum each technology's area potential per region into a DataFrame column,
    # skipping nodata/NaN pixels (as the previous groupby-sum did).
    columns = {}
    for area_potential_file in area_potentials:
        print(f"Processing area potential file: {area_potential_file}")
        with rasterio.open(area_potential_file) as src:
            # All technology mosaics must lie on the same grid, otherwise the
            # flat region index would silently aggregate the wrong pixels.
            assert (src.height, src.width) == reference_shape, (
                f"Raster shape of {area_potential_file} does not match {area_potentials[0]}"
            )
            assert src.transform == reference_transform, (
                f"Raster transform of {area_potential_file} does not match {area_potentials[0]}"
            )
            values = src.read(1, masked=True).ravel()[valid]
        weights = np.nan_to_num(values.filled(np.nan))
        columns[area_potential_file] = np.bincount(
            region_ids, weights=weights, minlength=len(shapes)
        )

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
