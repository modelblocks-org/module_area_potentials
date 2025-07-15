"""This script calculates the area potential based on the provided configuration."""

import click
import geo
import geopandas as gpd
import matplotlib.pyplot as plt
import xarray as xr
import yaml


@click.command()
@click.argument("shapes_path", type=str)
@click.argument("resampled_path", type=str)
@click.argument("config", type=str)
@click.argument("buffer_crs", type=str)
@click.argument("output_path", type=str)
@click.argument("plot_path", type=str)
def get_area_potential(
    shapes_path, resampled_path, config, buffer_crs, output_path, plot_path
):
    """Calculate the area potential based on the provided configuration.

    Args:
        shapes_path (str): Path to the input shapes in the parquet format.
        resampled_path (str): Path to the resampled input data in the NetCDF format.
        config (str): Configuration YAML string.
        buffer_crs (str): Coordinate Reference System for buffering shapes.
        output_path (str): Path to save the resulting area potential raster.
        plot_path (str): Path to save the plot of the area potential.

    Returns:
        None

    """
    shapes = gpd.read_parquet(shapes_path)
    ds = xr.open_dataset(resampled_path, decode_coords="all")
    # FIXME: this is a workaround for the CRS not being set correctly; not sure why
    ds.rio.write_crs(ds.spatial_ref.attrs["crs_wkt"], inplace=True)
    config = yaml.safe_load(config)

    # Start with the configured pixel area as a base
    potential_da = ds[config["initial_area"]].squeeze(drop=True)  # Drop `band`

    # Drop pixels from binary layers with share 0 from potential_da
    binary_layers = config.get("binary_layers", {})
    zero_binary_layers = [layer for layer, value in binary_layers.items() if value == 0]
    for layer in zero_binary_layers:
        if layer in ds:
            potential_da = potential_da.where(~(ds[layer] > 0))
        else:
            print(f"Warning: Layer '{layer}' not found in dataset. Skipping.")

    # Apply the continuous_layers criteria to drop additional pixels
    continuous_layers = config.get("continuous_layers", {})
    for layer, layer_config in continuous_layers.items():
        if layer in ds:
            # Apply the min-max criteria
            potential_da = potential_da.where(
                (ds[layer] <= layer_config["max"]) & (ds[layer] >= layer_config["min"])
            )
            # If a share is defined, multiply the pixel area by the share
            if "share" in layer_config:
                potential_da = potential_da * layer_config["share"]
        else:
            print(f"Warning: Layer '{layer}' not found in dataset. Skipping.")

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
                buffer = geo.apply_utm_buffer(
                    shapes_subset, buffer_distance_m=buffer_distance
                ).to_crs(ds.rio.crs)["geometry"]
            else:
                buffer = shapes_subset.to_crs(buffer_crs).buffer(buffer_distance)

            # Clip the potential area with the buffered shapes
            potential_da.rio.write_crs(ds.rio.crs, inplace=True)
            buffer_geo = gpd.GeoDataFrame(geometry=buffer).to_crs(ds.rio.crs)
            potential_da = potential_da.rio.clip(
                buffer_geo.geometry, buffer_geo.crs, invert=True
            )

    potential_da.name = "area_potential"
    potential_da = potential_da.transpose("band", "y", "x")
    potential_da.rio.write_crs(ds.rio.crs, inplace=True)
    potential_da.rio.to_raster(output_path, driver="GTiff", compress="LZW")

    potential_da.plot()
    plt.savefig(plot_path, bbox_inches="tight")


if __name__ == "__main__":
    get_area_potential()
