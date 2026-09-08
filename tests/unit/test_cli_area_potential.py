"""Reference and equivalence tests for the area_potential.py CLI.

Two safety nets for the planned mask/factor rewrite:

- reference tests pin the output rasters for configs covering every code path
  (both initial areas, continuous min/max with and without share, binary layers
  with value 0 / 1 / fractional, overlapping binary layers, buffering with a
  fixed CRS and with UTM, config overrides, missing layers);
- an oracle re-implementing the current *sequential* semantics is compared
  bit-exactly against the CLI output, including on randomized configs.
"""

import fixtures
import glom
import numpy as np
import pytest
import rioxarray as rxr
import xarray as xr
import yaml
from area_potential import get_area_potential

BINARY_OVERLAPPING = {
    "initial_area": "pixel_area",
    "binary_layers": {
        "regions_maritime": 0,
        "regions_land": 1,
        "protected": 0,
        "landcover_FARM": 0.1,
        "landcover_FOREST": 0,
        "landcover_URBAN": 0,
        "landcover_OTHER": 0.2,
        "landcover_NOT_SUITABLE": 0,
        "landcover_WATER": 0,
    },
}
CONTINUOUS_WITH_SHARE = {
    "initial_area": "settlement_area",
    "continuous_layers": {"settlement_share": {"min": 0.001, "max": 1, "share": 0.8}},
    "binary_layers": {"regions_maritime": 0, "regions_land": 1, "protected": 0},
}
CONTINUOUS_NO_SHARE = {
    "initial_area": "pixel_area",
    "continuous_layers": {"slope_deg": {"min": 0, "max": 10}},
    "binary_layers": {"regions_land": 1, "protected": 0},
}
OFFSHORE_BUFFERED = {
    "initial_area": "pixel_area",
    "continuous_layers": {"bathymetry": {"min": -60, "max": 0, "share": 0.9}},
    "binary_layers": {"regions_land": 0, "regions_maritime": 1},
    "shapes_buffer": {"land": 1500},
}
MISSING_LAYERS = {
    "initial_area": "pixel_area",
    "continuous_layers": {"not_a_continuous_layer": {"min": 0, "max": 1}},
    "binary_layers": {
        "not_a_binary_layer": 0,
        "also_missing": 1,
        "regions_land": 1,
        "protected": 0,
    },
}

# case id -> (config, buffer_crs, override config or None)
CASES = {
    "binary_overlapping": (BINARY_OVERLAPPING, "epsg:8857", None),
    "continuous_with_share": (CONTINUOUS_WITH_SHARE, "epsg:8857", None),
    "continuous_no_share": (CONTINUOUS_NO_SHARE, "epsg:8857", None),
    "offshore_buffer_epsg": (OFFSHORE_BUFFERED, "epsg:8857", None),
    "offshore_buffer_utm": (OFFSHORE_BUFFERED, "utm", None),
    "override_merge": (
        BINARY_OVERLAPPING,
        "epsg:8857",
        {"binary_layers": {"landcover_FARM": 0.5}},
    ),
    "missing_layers_warn": (MISSING_LAYERS, "epsg:8857", None),
}
UNBUFFERED_CASES = [case for case in CASES if "buffer" not in case]


def _run_area_potential(world, resampled_path, tmp_path, config, buffer_crs, override):
    """Run the CLI, returning (output DataArray, CLI output text)."""
    tif_path = tmp_path / "area_potential.tif"
    args = [world["shapes"], resampled_path, yaml.dump(config), buffer_crs, tif_path]
    if override is not None:
        args.append(f"--override_config={yaml.dump(override)}")
    result = fixtures.run_cli(get_area_potential, args)
    return rxr.open_rasterio(tif_path), result.output


def _parsed_config(config, override):
    """The config exactly as the CLI sees it (YAML round-trip plus glom merge)."""
    config = yaml.safe_load(yaml.dump(config))
    if override is not None:
        config = glom.merge([config, yaml.safe_load(yaml.dump(override))])
    return config


def sequential_area_potential(ds, config):
    """Oracle mirroring the current sequential where-chain (without buffering).

    The CLI writes float32 rasters, so oracle expectations are cast to float32
    before comparison — bit-exactness is required at the output granularity.
    """
    potential = ds[config["initial_area"]].squeeze(drop=True)
    binary_layers = config.get("binary_layers", {})
    for layer, value in binary_layers.items():
        if value == 0 and layer in ds:
            potential = potential.where(~(ds[layer] > 0), other=0)
    for layer, layer_config in config.get("continuous_layers", {}).items():
        if layer in ds:
            potential = potential.where(
                (ds[layer] <= layer_config["max"]) & (ds[layer] >= layer_config["min"]),
                other=0,
            )
            if "share" in layer_config:
                potential = potential * layer_config["share"]
    for layer, value in binary_layers.items():
        if layer in ds and value != 0:
            potential = xr.where(
                ds[layer] != 0, potential * ds[layer] * value, potential
            )
    return potential


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_area_potential_reference(case_id, world, resampled_path, tmp_path, reference):
    """The output raster matches the committed reference data for each config."""
    config, buffer_crs, override = CASES[case_id]
    da, _ = _run_area_potential(
        world, resampled_path, tmp_path, config, buffer_crs, override
    )
    reference.check_arrays(f"area_potential_{case_id}", {"values": da.values})


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_area_potential_invariants(case_id, world, resampled_path, tmp_path):
    """Output rasters are (band, y, x), NaN-free, non-negative, with nodata -1."""
    config, buffer_crs, override = CASES[case_id]
    da, _ = _run_area_potential(
        world, resampled_path, tmp_path, config, buffer_crs, override
    )
    assert da.dims == ("band", "y", "x")
    assert da.rio.nodata == -1
    values = da.values
    assert not np.isnan(values).any()
    assert ((values >= 0) | (values == -1)).all()


def test_area_potential_warns_on_missing_layers(world, resampled_path, tmp_path):
    """Layers absent from the dataset are skipped with a warning."""
    config, buffer_crs, override = CASES["missing_layers_warn"]
    _, output = _run_area_potential(
        world, resampled_path, tmp_path, config, buffer_crs, override
    )
    assert "Warning: Layer 'not_a_binary_layer' not found" in output
    assert "Warning: Layer 'not_a_continuous_layer' not found" in output


def test_area_potential_buffer_removes_nearshore_pixels(
    world, resampled_path, tmp_path
):
    """Buffering land shapes clips pixels out of the offshore potential."""
    config, buffer_crs, _ = CASES["offshore_buffer_epsg"]
    buffered, _ = _run_area_potential(
        world, resampled_path, tmp_path, config, buffer_crs, None
    )
    unbuffered_config = {k: v for k, v in config.items() if k != "shapes_buffer"}
    unbuffered, _ = _run_area_potential(
        world, resampled_path, tmp_path, unbuffered_config, buffer_crs, None
    )
    n_valid_buffered = int((buffered.values != -1).sum())
    n_valid_unbuffered = int((unbuffered.values != -1).sum())
    assert 0 < n_valid_buffered < n_valid_unbuffered


@pytest.mark.parametrize("case_id", UNBUFFERED_CASES)
def test_area_potential_matches_sequential_oracle(
    case_id, world, resampled_path, tmp_path
):
    """CLI output equals the sequential oracle bit-for-bit (no buffering)."""
    config, buffer_crs, override = CASES[case_id]
    da, _ = _run_area_potential(
        world, resampled_path, tmp_path, config, buffer_crs, override
    )
    with xr.open_dataset(resampled_path, decode_coords="all") as ds:
        expected = sequential_area_potential(
            ds.load(), _parsed_config(config, override)
        )
    expected = expected.transpose("band", "y", "x").fillna(-1.0)
    np.testing.assert_array_equal(da.values, expected.values.astype(np.float32))


def test_area_potential_inclusive_min_max_boundaries(world, resampled_path, tmp_path):
    """Continuous min/max bounds are inclusive.

    The bounds are taken from exact data values, so that an accidental switch
    to strict comparisons in a rewrite changes the output and fails this test.
    """
    with xr.open_dataset(resampled_path, decode_coords="all") as ds:
        ds = ds.load()
    slope = np.squeeze(ds["slope_deg"].values)
    finite = np.unique(slope[np.isfinite(slope)])
    config = {
        "initial_area": "pixel_area",
        "continuous_layers": {
            "slope_deg": {"min": float(finite[1]), "max": float(finite[-2])}
        },
        "binary_layers": {"protected": 0},
    }
    da, _ = _run_area_potential(
        world, resampled_path, tmp_path, config, "epsg:8857", None
    )
    expected = sequential_area_potential(ds, _parsed_config(config, None))
    expected = expected.transpose("band", "y", "x").fillna(-1.0)
    np.testing.assert_array_equal(da.values, expected.values.astype(np.float32))
    # Pixels lying exactly on the bounds must survive the min/max filter.
    values = np.squeeze(da.values)
    on_boundary = (slope == finite[1]) | (slope == finite[-2])
    assert (values[on_boundary] > 0).any()


def _random_config(rng, ds):
    """A random but valid tech config referencing existing layers."""
    binary_pool = sorted(
        name
        for name in ds.data_vars
        if name.startswith("landcover_")
        or name in ["regions_land", "regions_maritime", "protected"]
    )
    continuous_pool = ["slope_deg", "settlement_share", "bathymetry"]
    config = {
        "initial_area": str(rng.choice(["pixel_area", "settlement_area"])),
        # Always include one banded layer: the CLI requires the band dimension
        # to be broadcast back into the potential.
        "binary_layers": {"landcover_FARM": float(rng.choice([0.0, 1.0, 0.3]))},
    }
    for layer in rng.choice(binary_pool, size=3, replace=False):
        config["binary_layers"][str(layer)] = float(rng.choice([0.0, 1.0, 0.3, 2.0]))
    config["continuous_layers"] = {}
    for layer in rng.choice(
        continuous_pool, size=int(rng.integers(1, 3)), replace=False
    ):
        low, high = np.nanquantile(ds[str(layer)].values, [0.2, 0.8])
        layer_config = {"min": float(low), "max": float(high)}
        if rng.random() < 0.5:
            layer_config["share"] = float(rng.uniform(0.1, 0.9))
        config["continuous_layers"][str(layer)] = layer_config
    return config


@pytest.mark.parametrize("seed", range(4))
def test_area_potential_matches_sequential_oracle_randomized(
    seed, world, resampled_path, tmp_path
):
    """Randomized configs also agree with the sequential oracle bit-for-bit."""
    with xr.open_dataset(resampled_path, decode_coords="all") as ds:
        ds = ds.load()
    config = _random_config(np.random.default_rng(seed), ds)
    da, _ = _run_area_potential(
        world, resampled_path, tmp_path, config, "epsg:8857", None
    )
    expected = sequential_area_potential(ds, _parsed_config(config, None))
    expected = expected.transpose("band", "y", "x").fillna(-1.0)
    np.testing.assert_array_equal(da.values, expected.values.astype(np.float32))


def test_area_potential_all_excluded(world, resampled_path, tmp_path):
    """A config whose criteria exclude every pixel yields an all-zero raster."""
    config = {
        "initial_area": "pixel_area",
        # No slope value lies in this range, so every pixel is zeroed out
        # (pixels with NaN slope fail the comparison as well).
        "continuous_layers": {"slope_deg": {"min": 1e9, "max": 2e9}},
        "binary_layers": {"landcover_FARM": 1},
    }
    da, _ = _run_area_potential(
        world, resampled_path, tmp_path, config, "epsg:8857", None
    )
    with xr.open_dataset(resampled_path, decode_coords="all") as ds:
        expected = sequential_area_potential(ds.load(), _parsed_config(config, None))
    expected = expected.transpose("band", "y", "x").fillna(-1.0)
    np.testing.assert_array_equal(da.values, expected.values.astype(np.float32))
    assert (da.values == 0).all()


def test_area_potential_tiny_grid(world, resampled_path, tmp_path):
    """The CLI works on a 2x2-pixel dataset and agrees with the oracle."""
    with xr.open_dataset(resampled_path, decode_coords="all") as ds:
        ds = ds.load()
    # Anchor on a land pixel so that the potential is non-trivial.
    y_idx, x_idx = np.argwhere(np.squeeze(ds["regions_land"].values) == 1)[0]
    tiny = ds.isel(y=slice(y_idx, y_idx + 2), x=slice(x_idx, x_idx + 2))
    tiny_path = tmp_path / "tiny.nc"
    tiny.to_netcdf(tiny_path)
    config = {
        "initial_area": "pixel_area",
        "continuous_layers": {"slope_deg": {"min": 0, "max": 90, "share": 0.5}},
        "binary_layers": {"regions_land": 1, "landcover_FARM": 0.3},
    }
    da, _ = _run_area_potential(world, tiny_path, tmp_path, config, "epsg:8857", None)
    assert da.shape == (1, 2, 2)
    expected = sequential_area_potential(tiny, _parsed_config(config, None))
    expected = expected.transpose("band", "y", "x").fillna(-1.0)
    np.testing.assert_array_equal(da.values, expected.values.astype(np.float32))
