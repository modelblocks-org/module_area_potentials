def get_subunits(wildcards):
    checkpoint_output = checkpoints.breakup_shape.get(**wildcards).output[0]
    return expand(
        "<results>/{{shape}}/{{scenario}}/{subunit}/area_potential_{{tech}}.tif",
        subunit=glob_wildcards(
            os.path.join(checkpoint_output, "{subunit}.parquet")
        ).subunit,
    )


def get_techs(wildcards):
    return config["scenarios"][wildcards.scenario]["techs"].keys()


def uses_ship_travel(wildcards):
    """Return whether any scenario's techs or this subunit's overrides use ship travel."""
    tech_configs = []
    for scenario in config["scenarios"].values():
        tech_configs.extend(scenario["techs"].values())
        tech_configs.extend(
            scenario.get("overrides", {}).get(wildcards.subunit, {}).values()
        )
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


def get_subunit_potential_plots(wildcards):
    checkpoint_output = checkpoints.breakup_shape.get(**wildcards).output[0]
    return expand(
        "<results>/{{shape}}/{{scenario}}/{subunit}/area_potential_{tech}.png",
        subunit=glob_wildcards(
            os.path.join(checkpoint_output, "{subunit}.parquet")
        ).subunit,
        tech=get_techs(wildcards),
    )
