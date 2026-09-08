import shlex


rule prepare_resampled_inputs:
    input:
        script=workflow.source_path("../scripts/resample.py"),
        shapes=rules.breakup_shape.output,
        land_cover_path=rules.clip_landcover.output,
        slope_path=rules.clip_slope.output,
        settlement_path=rules.clip_settlement.output,
        bathymetry_path=rules.clip_bathymetry.output,
        protected_area_path=rules.rasterise_clip_wdpa.output,
        ship_travel_path=branch(
            condition=uses_ship_travel,
            then=rules.clip_ship_travel.output,
            otherwise=[],
        ),
    output:
        resampled_input="<resources>/automatic/resampled_inputs/{shape}/{subunit}.nc",
    log:
        "<logs>/{shape}/{subunit}/prepare_resampled_inputs.log",
    conda:
        "../envs/module.yaml"
    params:
        # Use internal defaults if not overridden
        land_cover_types_yaml_string=internal["land_cover_types"]
        | config.get("land_cover_types", {}),
        ship_travel_arg=lambda wildcards, input: (
            f"--ship-travel-path {shlex.quote(str(input.ship_travel_path))}"
            if input.ship_travel_path
            else ""
        ),
    message:
        "Resample inputs for {wildcards.subunit} in {wildcards.shape} to the projection and resolution of the land cover data, while aggregating land cover types."
    shell:
        """
        python {input.script:q} \
            "{input.shapes}/{wildcards.subunit}.parquet" \
            {input.land_cover_path:q} {input.slope_path:q} {input.settlement_path:q} {input.bathymetry_path:q} {input.protected_area_path:q} \
            {params.land_cover_types_yaml_string:q} \
            {output.resampled_input:q} \
            {params.ship_travel_arg} >{log:q} 2>&1
        """


rule plot_resampled_inputs:
    input:
        rules.prepare_resampled_inputs.output.resampled_input,
    output:
        report(
            "<resources>/automatic/resampled_inputs/{shape}/{subunit}.png",
            category="resampled_input",
        ),
    log:
        "<logs>/{shape}/{subunit}/plot_resampled_inputs.log",
    conda:
        "../envs/module.yaml"
    message:
        "Plot resampled inputs for {wildcards.subunit} in {wildcards.shape}."
    script:
        "../scripts/nc_to_png.py"


rule area_potential:
    input:
        script=workflow.source_path("../scripts/area_potential.py"),
        shapes=rules.breakup_shape.output,
        resampled_path=rules.prepare_resampled_inputs.output.resampled_input,
    output:
        area_potential="<results>/{shape}/{subunit}/area_potential_{tech}.tif",
    log:
        "<logs>/{shape}/{subunit}/area_potential_{tech}.log",
    conda:
        "../envs/module.yaml"
    params:
        config=lambda wildcards: config["techs"][f"{wildcards.tech}"],
        subunit_override_config=lambda wildcards: config.get("overrides", {})
        .get(wildcards.subunit, {})
        .get(wildcards.tech, {}),
        buffer_crs=lambda wildcards: config["buffer_crs"],
    message:
        "Compute area potential for the tech {wildcards.tech} and {wildcards.subunit} in {wildcards.shape}."
    shell:
        """
        python {input.script:q} "{input.shapes}/{wildcards.subunit}.parquet" {input.resampled_path:q} {params.config:q} {params.buffer_crs:q} {output.area_potential:q} --override_config={params.subunit_override_config:q} >{log:q} 2>&1
        """


rule plot_area_potential:
    input:
        rules.area_potential.output.area_potential,
    output:
        report(
            "<results>/{shape}/{subunit}/area_potential_{tech}.png",
            category="area_potential",
        ),
    log:
        "<logs>/{shape}/{subunit}/plot_area_potential_{tech}.log",
    conda:
        "../envs/module.yaml"
    message:
        "Plot area potential for the tech {wildcards.tech} and {wildcards.subunit} in {wildcards.shape}."
    script:
        "../scripts/tif_to_png.py"


rule aggregate_area_potential:
    input:
        get_subunits,
    output:
        aggregated_area_potential="<area_potential>",
    log:
        "<logs>/{shape}/aggregate_area_potential_{tech}.log",
    conda:
        "../envs/module.yaml"
    message:
        "Aggregate area potential for the tech {wildcards.tech} in {wildcards.shape}."
    shell:
        """
        gdalwarp --config GDAL_CACHEMAX 3000 -wm 3000 -multi -wo NUM_THREADS=ALL_CPUS -of GTiff -co COMPRESS=LZW -co PREDICTOR=3 {input} {output.aggregated_area_potential:q} >{log:q} 2>&1
        """


rule plot_aggregated_area_potential:
    input:
        rules.aggregate_area_potential.output.aggregated_area_potential,
    output:
        report(
            "<results>/{shape}/area_potential_{tech}.png",
            category="area_potential_plot",
        ),
    log:
        "<logs>/{shape}/plot_aggregated_area_potential_{tech}.log",
    conda:
        "../envs/module.yaml"
    message:
        "Plot aggregated area potential for the tech {wildcards.tech} in {wildcards.shape}."
    script:
        "../scripts/tif_to_png.py"


rule area_potential_report:
    input:
        shapes=rules.normalise_shapes.output.shapes,
        area_potentials=expand(
            workflow.pathvars.apply("<area_potential>"),
            tech=config["techs"].keys(),
            allow_missing=True,
        ),
        area_potential_plots=expand(
            "<results>/{{shape}}/area_potential_{tech}.png",
            tech=config["techs"].keys(),
        ),
        # Not used by the report itself: pulls in the per-subunit diagnostic
        # plots, which run in parallel jobs off the area_potential critical path
        resampled_input_plots=get_subunit_input_plots,
        subunit_potential_plots=get_subunit_potential_plots,
    output:
        csv="<results>/{shape}/area_potential_report.csv",
        html=report(
            "<results>/{shape}/area_potential_report.html",
            category="area_potential_report_table",
        ),
    log:
        "<logs>/{shape}/area_potential_report.log",
    conda:
        "../envs/module.yaml"
    message:
        "Generate an overview report of the area potential for all techs in shapes {wildcards.shape}."
    script:
        "../scripts/report.py"
