BASE_DIR = workflow.basedir

wildcard_constraints:
    tech="|".join(config["techs_onshore"].keys())

rule slope_too_steep:
    message:
        "Get areas with slope values greater than max_slope, i.e. too steep/not suitable for the tech {wildcards.tech}.",
    params:
        max_slope=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]["max_slope"]
    input:
        shapes=rules.download_cutout_slope.output,
    output:
        "resources/tmp/slope_too_steep_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {BASE_DIR}/scripts/get_slope_too_steep.py {input} {params.max_slope} {output}"

rule suitable_land_cover:
    message:
        "Get suitable land cover types for the tech {wildcards.tech}.",
    params:
        suitable_land_cover_types=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]["land_cover"]
    input:
        shapes=rules.cutout_landcover.output,
    output:
        "resources/tmp/suitable_land_cover_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {BASE_DIR}/scripts/get_suitable_land_cover_types.py {input} {params.suitable_land_cover_types} {output}"

rule resample_same_resolution:
    message:
        "Resample slope, land cover, and settlement to the same resolution for the tech {wildcards.tech}.",
    params:
        specs=config["specs"]
        suitable_land_cover_types=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]["land_cover"]
    input:
        shapes_path="resources/user/shapes.parquet",
        slope_path=rules.slope_too_steep.output,
        land_cover_path=rules.suitable_land_cover.output,
        settlement_path=rules.cutout_settlement.output,
    output:
        pixel_area="resources/tmp/pixel_area.nc",
        resampled="resources/tmp/resampled_input_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {BASE_DIR}/scripts/resample.py {input.shapes_path} {params.specs} {params.suitable_land_cover_types} {input.slope_path} {input.land_cover_path} {input.settlement_path} {output.pixel_area} {output.resampled}"

rule technical_mask:
    message:
        "Get areas with slope values greater than max_slope, i.e. too steep/not suitable for the tech {wildcards.tech}.",
    params:
        technical_mask=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]
    input:
        pixel_area_path=rules.resample_same_resolution.output.pixel_area,
        resampled_path=rules.resample_same_resolution.output.resampled,
    output:
        "resources/tmp/technical_masked_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {BASE_DIR}/scripts/apply_technical_mask.py {input.resampled_path} {input.pixel_area_path} {params.technical_mask} {output}"

rule area_potential:
    message:
        "Get areas with slope values greater than max_slope, i.e. too steep/not suitable for the tech {wildcards.tech}.",
    params:
        technical_mask=lambda wildcards: config["techs_onshore"][f"{wildcards.tech}"]
    input:
        masked_path=rules.technical_mask.output,
        pixel_area_path=rules.resample_same_resolution.output.pixel_area,
        protected_area_path=rules.unzip_wdpa.output,
        shapes_path="resources/user/shapes.parquet",
    output:
        "results/area_potential_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {BASE_DIR}/scripts/get_area_potential.py {input.masked_path} {input.pixel_area_path} {params.technical_mask} {input.protected_area_path} {input.shapes_path} {output}"