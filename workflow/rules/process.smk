wildcard_constraints:
    tech_onshore="|".join(config["techs_onshore"].keys()),
    tech_offshore="|".join(config["techs_offshore"].keys()),

rule resample_same_resolution:
    message:
        "Resample inputs to the projection and resolution of the land cover data, while aggregating land cover types.",
    input:
        script=workflow.source_path("../scripts/resample.py"),
        shapes="resources/user/shapes.parquet",
        land_cover_path=rules.cutout_landcover.output,
        slope_path=rules.download_cutout_slope.output,
        settlement_path=rules.cutout_settlement.output,
        protected_area_path=rules.unzip_wdpa.output,
    output:
        resampled_input="resources/resampled_inputs.nc",
        plot=report(
            "resources/resampled_inputs.pdf",
            category="resampled_input",
        ),
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" \
        "{input.shapes}" "{input.land_cover_path}" "{input.slope_path}" "{input.settlement_path}" "{input.protected_area_path}" \
        "{output.resampled_input}" "{output.plot}"
        """

rule technical_mask_onshore:
    message:
        "Get fraction satisfied all technical criteria: not too steep slope, suitable land cover, and not exceeding max_settlement for the tech {wildcards.tech_onshore}.",
    params:
        suitable_land_cover_types=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]["land_cover"],
        max_slope=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]["max_slope"],
        max_settlement=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]["settlement"]["max_settlement"],
    input:
        script=workflow.source_path("../scripts/apply_technical_mask.py"),
        resampled_path=rules.resample_same_resolution.output.resampled_input,
    output:
        technical_mask="resources/technical_mask_{tech_onshore}.nc",
        # plot=report(
        #     "resources/technical_mask_{tech_onshore}.pdf",
        #     category="technical_mask",
        # ),
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.resampled_path}" "{params.suitable_land_cover_types}" "{params.max_slope}" "{params.max_settlement}" "{output}"
        """

rule area_potential_onshore:
    message:
        "Apply weights then calculate the potential area for the tech {wildcards.tech_onshore}.",
    params:
        technical_mask=lambda wildcards: config["techs_onshore"][f"{wildcards.tech_onshore}"]
    input:
        script=workflow.source_path("../scripts/potential_onshore.py"),
        shapes="resources/user/shapes.parquet",
        masked_path=rules.technical_mask_onshore.output.technical_mask,
    output:
        area_potential="results/area_potential_{tech_onshore}.nc",
        plot=report(
            "results/area_potential_{tech_onshore}.png",
            category="area_potential",
        ),
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.masked_path}" "{params.technical_mask}" "{input.shapes}" "{output.area_potential}" "{output.plot}"
        """

rule area_potential_offshore:
    message:
        "Get area potential for the tech {wildcards.tech_offshore}"
    params:
        water_depth=lambda wildcards: config["techs_offshore"][f"{wildcards.tech_offshore}"]["water_depth"],
        weight=lambda wildcards: config["techs_offshore"][f"{wildcards.tech_offshore}"]["weight"],
    input:
        script=workflow.source_path("../scripts/potential_offshore.py"),
        shapes="resources/user/shapes.parquet",
        bathymetry_path=rules.download_cutout_bathymetry.output,
        resampled_input_path=rules.resample_same_resolution.output.resampled_input,
    output:
        area_potential="results/area_potential_{tech_offshore}.nc",
        plot=report(
            "results/area_potential_{tech_offshore}.png",
            category="area_potential",
        ),
    log:
        "logs/area_potential_{tech_offshore}.log",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.shapes}" \
        "{input.bathymetry_path}" "{params.water_depth}" "{input.resampled_input_path}" "{params.weight}" "{output.area_potential}" "{output.plot}" 2> "{log}"
        """


rule area_potential_report:
    message:
        "Generate an overview report of the area potential for all techs.",
    input:
        shapes="resources/user/shapes.parquet",
        resampled_path=rules.resample_same_resolution.output.resampled_input,
        area_potentials=expand(
            "results/area_potential_{tech}.nc",
            tech=config["techs_offshore"].keys(),
        ) + expand(
            "results/area_potential_{tech}.nc",
            tech=config["techs_onshore"].keys(),
        ),
    output:
        csv="results/area_potential_report.csv",
        html=report(
            "results/area_potential_report.html",
            category="area_potential_report",
        ),
    conda:
        "../envs/default.yaml"
    script:
        "../scripts/report.py"
