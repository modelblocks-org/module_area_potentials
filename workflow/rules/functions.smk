def get_subunits(wildcards):
    checkpoint_output = checkpoints.breakup_shape.get(**wildcards).output[0]
    return expand(
        "<results>/{{shape}}/{subunit}/area_potential_{{tech}}.tif",
        subunit=glob_wildcards(
            os.path.join(checkpoint_output, "{subunit}.parquet")
        ).subunit,
    )


def uses_ship_travel(wildcards):
    """Return whether a base tech or this subunit's overrides use ship travel."""
    tech_configs = list(config.get("techs", {}).values())
    tech_configs.extend(config.get("overrides", {}).get(wildcards.subunit, {}).values())
    return any(
        "ship_travel" in tech_config.get("continuous_layers", {})
        for tech_config in tech_configs
    )


def get_subunit_input_plots(wildcards):
    checkpoint_output = checkpoints.breakup_shape.get(**wildcards).output[0]
    return expand(
        "<resources>/automatic/resampled_inputs/{{shape}}/{subunit}.png",
        subunit=glob_wildcards(
            os.path.join(checkpoint_output, "{subunit}.parquet")
        ).subunit,
    )
