"""Break up shape."""

from pathlib import Path

import click
import geopandas as gpd
from _schemas import Shapes


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("split_by", type=str)
@click.argument("output_path", type=str)
def breakup_shape(shapes_path, split_by, output_path):
    """Break subunits out of shape and save the resulting shapefiles.

    Args:
        shapes_path (str): Path to the input shapes in the parquet format.
        split_by (str): Column on which to split the shapes.
        output_path (str): Path to save the resulting broken-up shapes.
        output_list_of_subunits (str): Path to save the list of subunits.

    Returns:
        None
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    shapes = gpd.read_parquet(shapes_path)
    shapes = Shapes.validate(shapes)

    # Print rows where geometry is empty
    if shapes.geometry.is_empty.any():
        print("Warning: The following rows have empty geometries and will be removed:")
        print(shapes[shapes.geometry.is_empty])
        shapes = shapes[~shapes.geometry.is_empty]

    if split_by == "none":
        subunits = ["all"]
        shapes.to_parquet(Path(output_path / "all.parquet"))

    else:
        subunits = sorted(shapes[split_by].unique())
        for subunit in subunits:
            sub_shapes = shapes[shapes[split_by] == subunit]
            if sub_shapes.empty:
                raise ValueError(f"No shapes found for {split_by}: {subunit}")

            sub_shapes.to_parquet(output_path / f"{subunit}.parquet")


if __name__ == "__main__":
    breakup_shape()
