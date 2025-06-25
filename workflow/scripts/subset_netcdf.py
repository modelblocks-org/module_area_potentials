import click
import geopandas as gpd
import xarray as xr


@click.command()
@click.argument("shapes_path")
@click.argument("netcdf_path")
@click.argument("output_path")
def subset_netcdf(shapes_path, netcdf_path, output_path):
    shapes = gpd.read_parquet(shapes_path)
    minlon, minlat, maxlon, maxlat = shapes.total_bounds
    opendap_ds = xr.open_dataset(netcdf_path)
    subset = opendap_ds.sel(lat=slice(minlat, maxlat), lon=slice(minlon, maxlon))
    subset.to_netcdf(output_path)


if __name__ == "__main__":
    subset_netcdf()
