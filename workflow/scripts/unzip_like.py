"""Emulates the `unzip` command across platforms."""

import os
import zipfile

import click


@click.command()
@click.argument("zip_path", type=click.Path(exists=True))
@click.option(
    "--target",
    "-t",
    type=click.Path(),
    default=".",
    help="Target directory to extract to.",
)
@click.option("--file", "-f", help="Specific file inside the zip to extract.")
def unzip(zip_path, target, file):
    """Emulates the `unzip` command across platforms.

    ZIP_PATH: Path to the .zip file
    """
    os.makedirs(target, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        if file:
            # Check if file exists in zip
            if file not in zip_ref.namelist():
                click.echo(f"Error: '{file}' not found in archive.")
                return
            zip_ref.extract(file, target)
            click.echo(f"Extracted '{file}' to '{target}'.")
        else:
            zip_ref.extractall(target)
            click.echo(f"Extracted all files to '{target}'.")


if __name__ == "__main__":
    unzip()
