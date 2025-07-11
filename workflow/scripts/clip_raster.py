"""Clip raster files based on the bounding box from a parquet shapefile."""

import subprocess

import click


@click.command()
@click.argument("input_tif", type=click.Path(exists=True))
@click.argument("input_parquet", type=click.Path(exists=True))
@click.argument("output_tif", type=click.Path())
def clip_raster(input_tif, input_parquet, output_tif):
    """Clip INPUT_TIF using the bounding box from INPUT_PARQUET and save as OUTPUT_TIF.

    This script calls 'fio' and 'rio' directly, assuming they are installed.

    """
    try:
        # Step 1: Get bounds from the input_parquet using fio
        fio_cmd = ["fio", "info", input_parquet, "--bounds"]
        result = subprocess.run(fio_cmd, capture_output=True, text=True, check=True)
        bounds = result.stdout.strip()

        # Step 2: Run rio clip with the bounds obtained
        rio_cmd = [
            "rio",
            "clip",
            "--overwrite",
            input_tif,
            output_tif,
            "--bounds",
            bounds,
        ]
        subprocess.run(rio_cmd, check=True)

    except subprocess.CalledProcessError as e:
        click.echo(f"Error running command: {e.cmd}", err=True)
        click.echo(e.stderr, err=True)


if __name__ == "__main__":
    clip_raster()
