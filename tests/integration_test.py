"""Set of standard Modelblocks tests.

PLEASE ENSURE THIS SET OF MINIMAL TESTS WORKS BEFORE PUBLISHING YOUR MODULE.
Contents may be updated in future template updates.
"""

import csv
import math
import subprocess
import tomllib
from pathlib import Path

import pytest
from clio_tools.data_module import ModuleInterface

INTEGRATION_TECHS = ["pv_rooftop", "pv_open_field", "wind_onshore", "wind_offshore"]


@pytest.fixture(scope="module")
def pixi_platforms(module_path) -> list[str]:
    """Pixi platforms defined for this project."""
    with (module_path / "pixi.toml").open("rb") as pixi_config:
        return tomllib.load(pixi_config)["workspace"]["platforms"]


def test_snakemake_environments(module_path, pixi_platforms, tmp_path):
    """All Snakemake environment files should be based on pixi counterparts."""
    env_dir = module_path / "workflow/envs"
    env_files = sorted(env_dir.glob("*.yaml"))
    assert env_files, f"No conda environments found in {module_path}."

    for env_file in env_files:
        env_name = env_file.stem

        output_dir = tmp_path / env_name
        subprocess.run(
            ["pixi", "run", "export-snakemake-env", env_name, str(output_dir)],
            check=True,
            cwd=module_path,
        )

        generated_yaml = output_dir / env_file.name
        assert generated_yaml.read_text() == env_file.read_text()

        for platform in pixi_platforms:
            pin_file = env_dir / f"{env_name}.{platform}.pin.txt"
            assert pin_file.exists(), f"{env_name} has no conda pins for {platform}"


def test_interface_file(module_path):
    """The interfacing file should be correct."""
    assert ModuleInterface.from_yaml(module_path / "INTERFACE.yaml")


@pytest.mark.parametrize(
    "file",
    [
        "AUTHORS",
        "CITATION.cff",
        "INTERFACE.yaml",
        "LICENSE",
        "README.md",
        "config/config.yaml",
        "workflow/internal/config.schema.yaml",
        "tests/integration/Snakefile",
    ],
)
def test_standard_file_existance(module_path, file):
    """Check that a minimal set of files used for documentation are present."""
    assert Path(module_path / file).exists()


def test_snakemake_all_failure(module_path):
    """The snakemake 'all' rule should return an error by default."""
    process = subprocess.run(
        "snakemake --cores 1", shell=True, cwd=module_path, capture_output=True
    )
    assert "INVALID" in str(process.stderr)


def test_snakemake_integration_testing(module_path):
    """Run a light-weight test simulating someone using this module."""
    assert subprocess.run(
        "snakemake --use-conda --cores 1",
        shell=True,
        check=True,
        cwd=module_path / "tests/integration",
    )


##
# Module-specific tests: compare the integration workflow outputs against
# committed reference data (regenerate deliberately via `pixi run update-reference`).
# These use only the standard library because the dev environment has no pandas.
##


def _report_csv_path(module_path):
    """Path of the report CSV produced by the integration workflow run."""
    path = (
        module_path
        / "tests/integration/resources/module/results/NLD/area_potential_report.csv"
    )
    assert path.exists(), (
        "Integration workflow outputs not found; "
        "test_snakemake_integration_testing must run (and pass) first."
    )
    return path


def _read_csv_rows(path):
    """Read a CSV file into a list of rows (lists of strings)."""
    with open(path, newline="") as f:
        return list(csv.reader(f))


def _cells_equal(actual, expected, rel_tol, abs_tol):
    """Compare two CSV cells, numerically where possible."""
    if actual == expected:
        return True
    try:
        actual_num, expected_num = float(actual), float(expected)
    except ValueError:
        return False
    if math.isnan(actual_num) and math.isnan(expected_num):
        return True
    return math.isclose(actual_num, expected_num, rel_tol=rel_tol, abs_tol=abs_tol)


def test_integration_output_files_exist(module_path):
    """The aggregated area potential rasters exist for every configured tech."""
    _report_csv_path(module_path)
    for tech in INTEGRATION_TECHS:
        tif = (
            module_path
            / f"tests/integration/results/outputs/NLD/area_potential_{tech}.tif"
        )
        assert tif.exists(), f"Missing output raster: {tif}"


def test_integration_output_values(module_path):
    """The report CSV matches the committed reference data cell by cell.

    Tolerances are deliberately tight: the workflow is expected to be
    reproducible from pinned inputs and pinned dependencies. Performance
    rewrites that change floating-point precision must relax these tolerances
    consciously, so the change is visible in review.
    """
    rel_tol, abs_tol = 1e-9, 1e-6
    actual_rows = _read_csv_rows(_report_csv_path(module_path))
    reference_csv = module_path / "tests/reference/NLD_area_potential_report.csv"
    assert reference_csv.exists(), (
        f"Missing reference data {reference_csv}; "
        "generate it with `pixi run update-reference-integration`."
    )
    expected_rows = _read_csv_rows(reference_csv)
    assert actual_rows[0] == expected_rows[0], "Report CSV header changed"
    assert len(actual_rows) == len(expected_rows), "Report CSV row count changed"
    mismatches = [
        f"row {i} column '{actual_rows[0][j]}': {actual!r} != reference {expected!r}"
        for i, (actual_row, expected_row) in enumerate(
            zip(actual_rows[1:], expected_rows[1:])
        )
        for j, (actual, expected) in enumerate(zip(actual_row, expected_row))
        if not _cells_equal(actual, expected, rel_tol, abs_tol)
    ]
    assert not mismatches, "Report differs from reference data:\n" + "\n".join(
        mismatches
    )


def test_integration_output_sanity(module_path):
    """Basic physical sanity of the report, independent of reference data."""
    rows = _read_csv_rows(_report_csv_path(module_path))
    header = rows[0]
    tech_columns = {
        tech: header.index(
            next(col for col in header if f"area_potential_{tech}" in col)
        )
        for tech in INTEGRATION_TECHS
    }
    class_column = header.index("shape_class")

    def values(tech, shape_class=None):
        return [
            float(row[tech_columns[tech]])
            for row in rows[1:]
            if row[tech_columns[tech]] not in ("", "nan")
            and (shape_class is None or row[class_column] == shape_class)
        ]

    for tech in INTEGRATION_TECHS:
        assert sum(values(tech)) > 0, f"No area potential at all for {tech}"
    # Offshore wind exists only in maritime regions; land techs only on land.
    assert sum(values("wind_offshore", "land")) == pytest.approx(0, abs=1e-6)
    for tech in ["pv_rooftop", "pv_open_field", "wind_onshore"]:
        assert sum(values(tech, "maritime")) == pytest.approx(0, abs=1e-6)
