"""Cut out the datasets to bounds determined by the input shapefile."""


rule cutout_landcover:
    message:
        "Cut land cover data to the bounds of the input shapefile."
    input:
        script=workflow.source_path("../scripts/clip_raster.py"),
        shapes="resources/user/shapes/{shape}.parquet",
        landcover=rules.unzip_globcover.output,
    output:
        "resources/automatic/cutout/{shape}/landcover.tif",
    log:
        "logs/{shape}/cutout_landcover.log",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.landcover}" "{input.shapes}" "{output}" 2> "{log}"
        """


rule cutout_settlement:
    message:
        "Cut settlement data to the bounds of the input shapefile."
    input:
        script=workflow.source_path("../scripts/clip_raster.py"),
        shapes="resources/user/shapes/{shape}.parquet",
        settlement=rules.unzip_ghsl.output,
    output:
        "resources/automatic/cutout/{shape}/settlement.tif",
    log:
        "logs/{shape}/cutout_settlement.log",
    conda:
        "../envs/default.yaml"
    shell:
        """
        python "{input.script}" "{input.settlement}" "{input.shapes}" "{output}" 2> "{log}"
        """
