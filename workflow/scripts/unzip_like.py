"""Emulates the `unzip` command across platforms."""

import os
import shutil
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
@click.option(
    "--file",
    "-f",
    help="Specific file inside the zip to extract.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output filename to save the extracted file as (used with -f).",
)
def unzip(zip_path, target, file, output):
    """Emulates the `unzip` command across platforms.

    ZIP_PATH: Path to the .zip file
    """
    os.makedirs(target, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        if file:
            if file not in zip_ref.namelist():
                click.echo(f"Error: '{file}' not found in archive.")
                return

            extracted_path = zip_ref.extract(file, target)

            if output:
                output_path = os.path.join(target, output)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.move(extracted_path, output_path)
                click.echo(f"Extracted '{file}' to '{output_path}'.")
            else:
                click.echo(f"Extracted '{file}' to '{extracted_path}'.")
        else:
            zip_ref.extractall(target)
            click.echo(f"Extracted all files to '{target}'.")


if __name__ == "__main__":
    unzip()
