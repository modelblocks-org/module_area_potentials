import click
import rioxarray as rxr


@click.command()
@click.argument("slope_path", type=str)
@click.argument("max_slope", type=int)
@click.argument("output_path", type=str)
def get_slope_too_steep(slope_path, max_slope, output_path):
    ds_slope = rxr.open_rasterio(slope_path)
    is_too_steep_slope = ds_slope > max_slope
    ds_out = is_too_steep_slope.to_dataset(name="slope_too_steep")
    ds_out.to_netcdf(output_path)


if __name__ == "__main__":
    get_slope_too_steep()
