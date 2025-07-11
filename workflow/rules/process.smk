rule prepare_resampled_inputs:
    message:
        "Resample inputs for {wildcards.shape} to the projection and resolution of the land cover data, while aggregating land cover types."
    input:
        script=workflow.source_path("../scripts/resample.py"),
        shapes="resources/user/shapes/{shape}.parquet",
        land_cover_path=rules.cutout_landcover.output,
        slope_path=rules.download_cutout_slope.output,
        settlement_path=rules.cutout_settlement.output,
        bathymetry_path=rules.download_cutout_bathymetry.output,
        protected_area_path="resources/user/wdpa.gdb",
    output:
        resampled_input="resources/automatic/{shape}.resampled_inputs.nc",
        plot=report(
            "resources/automatic/{shape}.resampled_inputs.png",
            category="resampled_input",
        ),
    log:
        "logs/{shape}/prepare_resampled_inputs.log",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" \
        "{input.shapes}" "{input.land_cover_path}" "{input.slope_path}" "{input.settlement_path}" "{input.bathymetry_path}" "{input.protected_area_path}" \
        "{output.resampled_input}" "{output.plot}" 2> "{log}"
        """


rule area_potential:
    message:
        "Compute area potential for the tech {wildcards.tech} and shapes {wildcards.shape}."
    params:
        config=lambda wildcards: config["techs"][f"{wildcards.tech}"],
        buffer_crs=lambda wildcards: config["buffer_crs"],
    input:
        script=workflow.source_path("../scripts/area_potential.py"),
        shapes="resources/user/shapes/{shape}.parquet",
        resampled_path=rules.prepare_resampled_inputs.output.resampled_input,
    output:
        area_potential="results/{shape}/area_potential_{tech}.tif",
        plot=report(
            "results/{shape}/area_potential_{tech}.png",
            category="area_potential",
        ),
    log:
        "logs/{shape}/area_potential_{tech}.log",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.shapes}" "{input.resampled_path}" "{params.config}" "{params.buffer_crs}" "{output.area_potential}" "{output.plot}" 2> "{log}"
        """


rule area_potential_report:
    message:
        "Generate an overview report of the area potential for all techs in shapes {wildcards.shape}."
    input:
        shapes="resources/user/shapes/{shape}.parquet",
        resampled_path=rules.prepare_resampled_inputs.output.resampled_input,
        area_potentials=expand(
            "results/{{shape}}/area_potential_{tech}.tif",
            tech=config["techs"].keys(),
        ),
    output:
        csv="results/{shape}/area_potential_report.csv",
        html=report(
            "results/{shape}/area_potential_report.html",
            category="area_potential_report",
        ),
    log:
        "logs/{shape}/area_potential_report.log",
    conda:
        "../envs/default.yaml"
    script:
        "../scripts/report.py"
