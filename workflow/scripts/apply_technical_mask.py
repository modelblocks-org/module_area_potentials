import click
import rioxarray as rxr


@click.command()
@click.argument("resampled_path", type=str)
@click.argument("pixel_area_path", type=str)
@click.argument("technical_mask", type=int)
@click.argument("output_path", type=str)
def apply_technical_mask(resampled_path, pixel_area_path, technical_mask, output_path):
    ds_resampled = rxr.open_rasterio(resampled_path)

    # get fraction of settlement (built-up surface) compared to pixel area, both in m2
    pixel_area = rxr.open_rasterio(pixel_area_path)
    ds_resampled["settlement"] = ds_resampled["settlement"] / pixel_area

    # only keep pixel with fraction sum of suitable land cover >= 0.5,
    # too steep slope < 0.5
    # settlement <= max_settlement
    suitable_land_cover_types = [
        type != 0 for type in technical_mask["land_cover"].items
    ]
    land_cover_mask = (
        ds_resampled[suitable_land_cover_types].to_array().sum(dim="variable") >= 0.5
    )
    combined_mask = (
        (ds_resampled["slope"] < 0.5)
        & land_cover_mask
        & (ds_resampled["settlement"] <= technical_mask["settlement"]["max_settlement"])
    )
    ds_resampled = ds_resampled.where(combined_mask)
    ds_resampled.to_netcdf(output_path)


if __name__ == "__main__":
    apply_technical_mask()
