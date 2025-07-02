wildcard_constraints:
    tech_onshore="|".join(config["techs_onshore"].keys()),
    tech_offshore="|".join(config["techs_offshore"].keys()),

rule resample_same_resolution_onshore:
    message:
        "Resample slope, land cover (subset to suitable types), and settlement to the same resolution for the tech {wildcards.tech_onshore}.",
    params:
        projection=config["specs"]["projection"],
        resolution=config["specs"]["resolution"],
        suitable_land_cover_types=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]["land_cover"],
        max_slope=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]["max_slope"],
    input:
        script=workflow.source_path("../scripts/resample.py"),
        shapes="resources/user/shapes.parquet",
        slope_path=rules.download_cutout_slope.output,
        land_cover_path=rules.cutout_landcover.output,
        settlement_path=rules.cutout_settlement.output,
    output:
        "resources/resampled_input_{tech_onshore}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.shapes}" "{params.projection}" "{params.resolution}" \
        "{params.suitable_land_cover_types}" "{input.slope_path}" "{input.land_cover_path}" "{input.settlement_path}" "{params.max_slope}" \
        "{output}"
        """

rule technical_mask_onshore:
    message:
        "Get fraction satisfied all technical criteria: not too steep slope, suitable land cover, and not exceeding max_settlement for the tech {wildcards.tech_onshore}.",
    params:
        suitable_land_cover_types=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]["land_cover"],
        max_settlement=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]["settlement"]["max_settlement"],
    input:
        script=workflow.source_path("../scripts/apply_technical_mask.py"),
        resampled_path=rules.resample_same_resolution_onshore.output,
    output:
        "resources/technical_mask_{tech_onshore}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.resampled_path}" "{params.suitable_land_cover_types}" "{params.max_settlement}" "{output}"
        """

rule area_potential_onshore:
    message:
        "Apply weights, mask out protected area then calculate the potential area for the tech {wildcards.tech_onshore}.",
    params:
        technical_mask=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]
    input:
        script=workflow.source_path("../scripts/get_area_potential.py"),
        shapes="resources/user/shapes.parquet",
        masked_path=rules.technical_mask_onshore.output,
        protected_area_path=rules.unzip_wdpa.output,
    output:
        "results/area_potential_{tech_onshore}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.masked_path}" "{params.technical_mask}" "{input.protected_area_path}" "{input.shapes}" "{output}"
        """

rule area_potential_offshore:
    message:
        "Get area potential for the tech {wildcards.tech_offshore}"
    params:
        projection=config["specs"]["projection"],
        resolution=config["specs"]["resolution"],
        water_depth=lambda wildcards: config["techs_offshore"][f"{wildcards.tech_offshore}"]["water_depth"],
        weight=lambda wildcards: config["techs_offshore"][f"{wildcards.tech_offshore}"]["weight"],
    input:
        script=workflow.source_path("../scripts/wind_offshore.py"),
        shapes="resources/user/shapes.parquet",
        bathymetry_path=rules.download_cutout_bathymetry.output,
        land_sea_mask_path=rules.cutout_landseamask.output,
        protected_area_path=rules.unzip_wdpa.output,
    output:
        "results/area_potential_{tech_offshore}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.shapes}" "{params.projection}" "{params.resolution}" \
        "{input.bathymetry_path}" "{params.water_depth}" "{input.land_sea_mask_path}" \
        "{input.protected_area_path}" "{params.weight}" "{output}"
        """