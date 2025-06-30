wildcard_constraints:
    tech="|".join(config["techs_onshore"].keys())

rule slope_too_steep:
    message:
        "Get areas with slope values greater than max_slope, i.e. too steep/not suitable for the tech {wildcards.tech}.",
    params:
        max_slope=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]["max_slope"],
    input:
        script=workflow.source_path("../scripts/get_slope_too_steep.py"),
        shapes=rules.download_cutout_slope.output,
    output:
        "resources/automatic/slope_too_steep_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {input.script} {input.shapes} {params.max_slope} {output}"

rule suitable_land_cover:
    message:
        "Get suitable land cover types for the tech {wildcards.tech}.",
    params:
        suitable_land_cover_types=lambda wildcards: list(config["techs_onshore"][f"{wildcards.tech}"]["land_cover"].keys()),
    input:
        script=workflow.source_path("../scripts/get_suitable_land_cover_types.py"),
        shapes=rules.cutout_landcover.output,
    output:
        "resources/automatic/suitable_land_cover_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {input.script} {input.shapes} {params.suitable_land_cover_types} {output}"

rule resample_same_resolution:
    message:
        "Resample slope, land cover, and settlement to the same resolution for the tech {wildcards.tech}.",
    params:
        projection=config["specs"]["projection"],
        resolution=config["specs"]["resolution"],
        suitable_land_cover_types=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]["land_cover"],
    input:
        script=workflow.source_path("../scripts/resample.py"),
        shapes_path="resources/user/shapes.parquet",
        slope_path=rules.slope_too_steep.output,
        land_cover_path=rules.suitable_land_cover.output,
        settlement_path=rules.cutout_settlement.output,
    output:
        pixel_area="resources/automatic/pixel_area_{tech}.nc",
        resampled="resources/automatic/resampled_input_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.shapes_path}" "{params.projection}" "{params.resolution}" "{params.suitable_land_cover_types}" "{input.slope_path}" "{input.land_cover_path}" "{input.settlement_path}" "{output.pixel_area}" "{output.resampled}"
        """

rule technical_mask:
    message:
        "Get areas with slope values greater than max_slope, i.e. too steep/not suitable for the tech {wildcards.tech}.",
    params:
        technical_mask=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]
    input:
        script=workflow.source_path("../scripts/apply_technical_mask.py"),
        pixel_area_path=rules.resample_same_resolution.output.pixel_area,
        resampled_path=rules.resample_same_resolution.output.resampled,
    output:
        "resources/automatic/technical_masked_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {input.script} {input.resampled_path} {input.pixel_area_path} {params.technical_mask} {output}"

rule area_potential:
    message:
        "Get areas with slope values greater than max_slope, i.e. too steep/not suitable for the tech {wildcards.tech}.",
    params:
        technical_mask=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]
    input:
        script=workflow.source_path("../scripts/get_area_potential.py"),
        masked_path=rules.technical_mask.output,
        pixel_area_path=rules.resample_same_resolution.output.pixel_area,
        protected_area_path=rules.unzip_wdpa.output,
        shapes_path="resources/user/shapes.parquet",
    output:
        "results/area_potential_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {input.script} {input.masked_path} {input.pixel_area_path} {params.technical_mask} {input.protected_area_path} {input.shapes_path} {output}"