"""This script calculates the area potential based on the provided configuration."""

import _geo
import click
import geopandas as gpd
import glom
import matplotlib.pyplot as plt
import xarray as xr
import yaml
from _script_utils import plot_with_zero_separate


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("resampled_path", type=str)
@click.argument("config", type=str)
@click.argument("buffer_crs", type=str)
@click.argument("output_path", type=str)
@click.argument("plot_path", type=str)
@click.option("--override_config", type=str)
def get_area_potential(
    shapes_path,
    resampled_path,
    config,
    buffer_crs,
    output_path,
    plot_path,
    override_config,
):
    """Calculate the area potential based on the provided configuration.

    Args:
        shapes_path (str): Path to the input shapes in the parquet format.
        resampled_path (str): Path to the resampled input data in the NetCDF format.
        config (str): Configuration YAML string.
        buffer_crs (str): Coordinate Reference System for buffering shapes.
        output_path (str): Path to save the resulting area potential raster.
        plot_path (str): Path to save the plot of the area potential.
        override_config (str): Configuration override YAML string.

    Returns:
        None

    """
    shapes = gpd.read_parquet(shapes_path)
    ds = xr.open_dataset(resampled_path, decode_coords="all")
    # NOTE: this is a workaround for the CRS not being set correctly, ideally this
    # should not be necessary
    ds.rio.write_crs(ds.spatial_ref.attrs["crs_wkt"], inplace=True)
    config = yaml.safe_load(config)
    if override_config:
        override_config = yaml.safe_load(override_config)
        config = glom.merge([config, override_config])
        print(f"\nConfig after override: {config}\n")

    # Start with the configured pixel area as a base
    potential_da = ds[config["initial_area"]].squeeze(drop=True)  # Drop `band`

    # All zero-out criteria are accumulated into a single boolean keep-mask and
    # applied in one .where() call: boolean masks are cheap, while each
    # .where() on the potential would copy the full float array.
    keep = None

    def _all_of(mask, condition):
        return condition if mask is None else mask & condition

    # Zero out pixels from binary layers with share 0
    binary_layers = config.get("binary_layers", {})
    for layer, value in binary_layers.items():
        if value != 0:
            continue
        if layer in ds:
            keep = _all_of(keep, ~(ds[layer] > 0))
        else:
            print(f"Warning: Layer '{layer}' not found in dataset. Skipping.")

    # Zero out pixels outside the min-max criteria of the continuous layers
    continuous_layers = config.get("continuous_layers", {})
    for layer, layer_config in continuous_layers.items():
        if layer in ds:
            keep = _all_of(
                keep,
                (ds[layer] <= layer_config["max"]) & (ds[layer] >= layer_config["min"]),
            )
        else:
            print(f"Warning: Layer '{layer}' not found in dataset. Skipping.")

    if keep is not None:
        potential_da = potential_da.where(keep, other=0)

    # If a share is defined for a continuous layer, multiply the pixel area by
    # the share (in configuration order, to stay bit-identical with the
    # previous per-layer chain)
    for layer, layer_config in continuous_layers.items():
        if layer in ds and "share" in layer_config:
            potential_da = potential_da * layer_config["share"]

    # Multiply pixels by their share from the binary layers
    for layer, value in binary_layers.items():
        if layer in ds:
            if value != 0:
                potential_da = xr.where(
                    ds[layer] != 0, potential_da * ds[layer] * value, potential_da
                )
        else:
            print(f"Warning: Layer '{layer}' not found in dataset. Skipping.")

    # Apply shapes-based buffering
    if "shapes_buffer" in config:
        for shape_class in config["shapes_buffer"]:
            buffer_distance = config["shapes_buffer"][shape_class]
            shapes_subset = shapes[shapes["shape_class"] == shape_class]
            if buffer_crs.lower() == "utm":
                buffer = _geo.apply_utm_buffer(
                    shapes_subset, buffer_distance_m=buffer_distance
                ).to_crs(ds.rio.crs)["geometry"]
            else:
                buffer = shapes_subset.to_crs(buffer_crs).buffer(buffer_distance)

            # Clip the potential area with the buffered shapes. drop=False
            # keeps the output grid identical across techs (with drop=True the
            # raster is cropped to the inverse-mask extent) and skips the crop
            # work; clipped-out pixels become nodata.
            potential_da.rio.write_crs(ds.rio.crs, inplace=True)
            buffer_geo = gpd.GeoDataFrame(geometry=buffer).to_crs(ds.rio.crs)
            potential_da = potential_da.rio.clip(
                buffer_geo.geometry, buffer_geo.crs, invert=True, drop=False
            )

    potential_da.name = "area_potential"
    potential_da = potential_da.transpose("band", "y", "x")
    potential_da.rio.write_crs(ds.rio.crs, inplace=True)

    fig, ax = plt.subplots(1, 1)
    ax = plot_with_zero_separate(ax=ax, da=potential_da)
    plt.savefig(plot_path, bbox_inches="tight")

    # Fill NaN with a nodata value only after plotting.
    # float32 halves the file size and downstream I/O; per-pixel areas are at
    # most ~1e5 m2, where float32 error is below 0.01 m2. PREDICTOR=3 improves
    # LZW compression of float data.
    nodata_value = -1
    potential_da = potential_da.fillna(nodata_value).astype("float32")
    potential_da.rio.write_nodata(nodata_value, inplace=True)
    potential_da.rio.to_raster(
        output_path, driver="GTiff", compress="LZW", predictor=3, write_nodata=True
    )


if __name__ == "__main__":
    get_area_potential()
