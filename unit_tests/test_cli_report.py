"""Reference and oracle tests for report.py.

Guards the planned groupby-to-bincount rewrite of the per-region aggregation,
including the edge cases that rewrite must preserve: nodata pixels (NaN after
masking), pixels outside all regions, and a region too small to own any pixel.
"""

import fixtures
import numpy as np
import pandas as pd
import pytest
from rasterio.features import rasterize
from report import report

TECH_FILES = ["area_potential_tech_a.tif", "area_potential_tech_b.tif"]
NODATA = -1.0


def _write_potential_tif(path, rng):
    """A synthetic area-potential raster with zeros and nodata patches."""
    x, y = fixtures.grid_coords(fixtures.LANDCOVER_RESOLUTION)
    values = rng.uniform(0, 1e4, size=(len(y), len(x)))
    values[rng.random(values.shape) < 0.2] = 0.0
    values[rng.random(values.shape) < 0.1] = NODATA
    da = fixtures.make_raster(values, x, y, nodata=NODATA)
    da.rio.to_raster(path)


@pytest.fixture
def report_outputs(tmp_path, monkeypatch):
    """Run report() on synthetic tifs; returns (shapes, csv path, html path).

    Runs in tmp_path with relative tif paths so that the tif-derived column
    names in the CSV are stable for reference comparison.
    """
    monkeypatch.chdir(tmp_path)
    shapes = fixtures.make_shapes(include_subpixel_region=True)
    shapes.to_parquet("shapes.parquet")
    rng = np.random.default_rng(42)
    for tech_file in TECH_FILES:
        _write_potential_tif(tech_file, rng)
    report("shapes.parquet", TECH_FILES, "report.csv", "report.html")
    return shapes, tmp_path / "report.csv", tmp_path / "report.html"


def test_report_reference(report_outputs, reference):
    """The report CSV matches the committed reference data."""
    _, csv_path, _ = report_outputs
    reference.check_dataframe("report", csv_path)


def test_report_matches_naive_region_sums(report_outputs):
    """Per-region sums equal an independent mask-based aggregation."""
    shapes, csv_path, _ = report_outputs
    df = pd.read_csv(csv_path, index_col=0)
    for tech_file in TECH_FILES:
        da = fixtures.load_raster(tech_file).squeeze(drop=True)
        values = np.where(da.values == NODATA, np.nan, da.values)
        regions = rasterize(
            zip(shapes.geometry, shapes.index),
            out_shape=da.rio.shape,
            transform=da.rio.transform(),
            fill=-9999,
        )
        for region_index in [0, 1, 2]:
            expected = np.nansum(values[regions == region_index])
            assert df.loc[region_index, tech_file] == pytest.approx(expected, rel=1e-12)


def test_report_drops_pixel_free_regions(report_outputs):
    """A region too small to own a pixel does not appear in the report."""
    _, csv_path, _ = report_outputs
    df = pd.read_csv(csv_path, index_col=0)
    assert set(df.index) == {0.0, 1.0, 2.0}


def test_report_metadata_columns(report_outputs):
    """Shape metadata columns are aligned with the region raster indices."""
    shapes, csv_path, _ = report_outputs
    df = pd.read_csv(csv_path, index_col=0)
    assert list(df.columns[:4]) == [
        "shape_id",
        "country_id",
        "shape_class",
        "parent_name",
    ]
    for region_index in [0, 1, 2]:
        assert df.loc[region_index, "shape_id"] == shapes.loc[region_index, "shape_id"]


def test_report_writes_html_with_total_row(report_outputs):
    """The HTML report exists and contains the appended Total row."""
    _, _, html_path = report_outputs
    html = html_path.read_text()
    assert "Total" in html
