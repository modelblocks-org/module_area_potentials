"""Tests for the breakup_shape.py CLI."""

import fixtures
import geopandas as gpd
import pandas as pd
from breakup_shape import breakup_shape
from click.testing import CliRunner
from shapely.geometry import Polygon, box


def _two_country_shapes():
    """Four regions across two countries."""
    shapes = fixtures.make_shapes()
    extra = gpd.GeoDataFrame(
        {
            "shape_id": ["region_c"],
            "country_id": ["BBB"],
            "shape_class": ["land"],
            "parent_name": ["Parent of region_c"],
            "geometry": [box(6.0, 52.0, 6.1, 52.1)],
        },
        crs="EPSG:4326",
    )
    return pd.concat([shapes, extra], ignore_index=True)


def test_breakup_shape_splits_by_column(tmp_path):
    """Splitting by country_id writes one parquet file per country."""
    shapes_path = tmp_path / "shapes.parquet"
    _two_country_shapes().to_parquet(shapes_path)
    output_path = tmp_path / "subunits"
    fixtures.run_cli(breakup_shape, [shapes_path, "country_id", output_path])
    assert sorted(path.name for path in output_path.iterdir()) == [
        "AAA.parquet",
        "BBB.parquet",
    ]
    assert len(gpd.read_parquet(output_path / "AAA.parquet")) == 3
    assert len(gpd.read_parquet(output_path / "BBB.parquet")) == 1


def test_breakup_shape_split_by_none(tmp_path):
    """split_by 'none' writes everything to a single all.parquet."""
    shapes_path = tmp_path / "shapes.parquet"
    _two_country_shapes().to_parquet(shapes_path)
    output_path = tmp_path / "subunits"
    fixtures.run_cli(breakup_shape, [shapes_path, "none", output_path])
    assert [path.name for path in output_path.iterdir()] == ["all.parquet"]
    assert len(gpd.read_parquet(output_path / "all.parquet")) == 4


def test_breakup_shape_rejects_empty_geometries(tmp_path):
    """Current behaviour: ShapesSchema rejects empty geometries outright.

    (The post-validation empty-geometry removal branch in the script is
    unreachable; this test documents the de-facto contract.)
    """
    shapes = _two_country_shapes()
    shapes.loc[len(shapes)] = {
        "shape_id": "region_empty",
        "country_id": "BBB",
        "shape_class": "land",
        "parent_name": "Empty",
        "geometry": Polygon(),
    }
    shapes_path = tmp_path / "shapes.parquet"
    shapes.to_parquet(shapes_path)
    result = CliRunner().invoke(
        breakup_shape, [str(shapes_path), "country_id", str(tmp_path / "subunits")]
    )
    assert result.exit_code != 0
