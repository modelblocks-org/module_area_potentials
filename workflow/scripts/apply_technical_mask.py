import click
import xarray as xr
import yaml


@click.command()
@click.argument("resampled_path", type=str)
@click.argument("suitable_land_cover_types", type=str)
@click.argument("max_settlement", type=float)
@click.argument("output_path", type=str)
def apply_technical_mask(
    resampled_path,
    suitable_land_cover_types,
    max_settlement,
    output_path,
):
    ds_resampled = xr.open_dataset(resampled_path, engine="netcdf4")
    print("ds_resampled before applying technical mask", ds_resampled)

    # get fraction of settlement (built-up surface) compared to pixel area, both in m2
    ds_resampled["settlement"] = ds_resampled["settlement"] / ds_resampled["pixel_area"]
    print("ds_resampled after calculating settlement", ds_resampled)

    # only keep pixel with fraction sum of suitable land cover >= 0.5,
    # too steep slope < 0.5
    # settlement <= max_settlement
    suitable_land_cover_types = yaml.safe_load(suitable_land_cover_types)

    land_cover_types = [
        type for type, value in suitable_land_cover_types.items() if value != 0
    ]
    land_cover_mask = (
        ds_resampled[land_cover_types].to_array().sum(dim="variable") >= 0.5
    )

    combined_mask = (
        (ds_resampled["slope_too_steep"] <= 0.5)
        & land_cover_mask
        & (ds_resampled["settlement"] <= max_settlement)
    )
    ds_resampled = ds_resampled.where(combined_mask)
    print("ds_resampled before saving", ds_resampled)
    ds_resampled.to_netcdf(output_path)


if __name__ == "__main__":
    apply_technical_mask()
