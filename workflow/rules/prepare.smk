"""Cut out the datasets to bounds determined by the input shapefile."""

BASE_DIR = workflow.basedir

rule cutout_landcover:
    message:
        "Cut land cover data to the bounds of the input shapefile."
    input:
        shapes="resources/user/shapes.parquet",
        landcover=rules.unzip_globcover.output.landcover,
    output:
        "resources/cutout_landcover.tif",
    conda:
        "../envs/default.yaml"
    shell:
        """
        rio clip --overwrite "{input.landcover}" "{output}" --bounds "$(fio info '{input.shapes}' --bounds)"
        """

rule cutout_landseamask:
    message:
        "Cut land seamask data to the bounds of the input shapefile."
    input:
        shapes="resources/user/shapes.parquet",
        landseamask=rules.unzip_globcover.output.landseamask,
    output:
        "resources/cutout_landseamask.tif",
    conda:
        "../envs/default.yaml"
    shell:
        """
        rio clip --overwrite "{input.landseamask}" "{output}" --bounds "$(fio info '{input.shapes}' --bounds)"
        """


rule cutout_bathymetry:
    message:
        "Cut bathymetry data to the bounds of the input shapefile."
    input:
        shapes="resources/user/shapes.parquet",
        bathymetry=rules.merge_gebco.output,
    output:
        "resources/cutout_bathymetry.tif",
    conda:
        "../envs/default.yaml"
    shell:
        """
        rio clip --overwrite "{input.bathymetry}" "{output}" --bounds "$(fio info '{input.shapes}' --bounds)"
        """

rule cutout_settlement:
    message:
        "Cut settlement data to the bounds of the input shapefile."
    input:
        shapes="resources/user/shapes.parquet",
        settlement=rules.unzip_ghsl.output,
    output:
        "resources/cutout_settlement.tif",
    conda:
        "../envs/default.yaml"
    shell:
        """
        rio clip --overwrite "{input.settlement}" "{output}" --bounds "$(fio info '{input.shapes}' --bounds)"
        """
