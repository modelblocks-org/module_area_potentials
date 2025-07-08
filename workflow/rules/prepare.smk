"""Cut out the datasets to bounds determined by the input shapefile."""

rule cutout_landcover:
    message:
        "Cut land cover data to the bounds of the input shapefile."
    input:
        shapes="resources/user/shapes/{shape}.parquet",
        landcover=rules.unzip_globcover.output,
    output:
        "resources/cutout/{shape}/landcover.tif",
    conda:
        "../envs/default.yaml"
    shell:
        """
        rio clip --overwrite "{input.landcover}" "{output}" --bounds "$(fio info '{input.shapes}' --bounds)"
        """


rule cutout_settlement:
    message:
        "Cut settlement data to the bounds of the input shapefile."
    input:
        shapes="resources/user/shapes/{shape}.parquet",
        settlement=rules.unzip_ghsl.output,
    output:
        "resources/cutout/{shape}/settlement.tif",
    conda:
        "../envs/default.yaml"
    shell:
        """
        rio clip --overwrite "{input.settlement}" "{output}" --bounds "$(fio info '{input.shapes}' --bounds)"
        """
