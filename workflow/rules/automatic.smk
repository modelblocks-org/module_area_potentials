"""Rules to used to download automatic resource files."""

if config.get("tiny_files", False):

    ##
    # Directly download clipped slope and bathymetry data
    ##

    rule clip_slope:
        input:
            vector="resources/user/shapes/{shape}.parquet",
        output:
            path="resources/automatic/cutout/{shape}/slope.tif",
        log:
            "logs/{shape}/clip_slope.log",
        params:
            cog_url=internal["resources"]["automatic"]["slope"],
        message:
            "Download slope data covering the bounds of the input shapefile."
        wrapper:
            "v7.2.0/geo/rasterio/clip-geotiff"

    rule clip_bathymetry:
        input:
            vector="resources/user/shapes/{shape}.parquet",
        output:
            path="resources/automatic/cutout/{shape}/bathymetry.tif",
        log:
            "logs/{shape}/clip_bathymetry.log",
        params:
            cog_url=internal["resources"]["automatic"]["bathymetry"],
        message:
            "Download bathymetry data covering the bounds of the input shapefile."
        wrapper:
            "v7.2.0/geo/rasterio/clip-geotiff"

else:

    ##
    # Download global slope and bathymetry data, then clip the files locally
    ##

    rule download_slope:
        output:
            path="resources/automatic/global/slope.tif",
        log:
            "logs/download_slope.log",
        conda:
            "../envs/shell.yaml"
        params:
            url=internal["resources"]["automatic"]["slope"],
        message:
            "Download global slope data."
        shell:
            """
            curl -sSLo {output:q} {params.url:q}
            """

    rule download_bathymetry:
        output:
            path="resources/automatic/global/bathymetry.tif",
        log:
            "logs/download_bathymetry.log",
        conda:
            "../envs/shell.yaml"
        params:
            url=internal["resources"]["automatic"]["bathymetry"],
        message:
            "Download global bathymetry data."
        shell:
            """
            curl -sSLo {output:q} {params.url:q}
            """

    rule clip_slope:
        input:
            script=workflow.source_path("../scripts/clip_raster.py"),
            shapes="resources/user/shapes/{shape}.parquet",
            slope=rules.download_slope.output,
        output:
            "resources/automatic/cutout/{shape}/slope.tif",
        log:
            "logs/{shape}/clip_slope.log",
        conda:
            "../envs/default.yaml"
        message:
            "Cut slope data to the bounds of the input shapefile."
        shell:
            """
            python {input.script:q} {input.slope:q} {input.shapes:q} {output:q} 2>{log:q}
            """

    rule clip_bathymetry:
        input:
            script=workflow.source_path("../scripts/clip_raster.py"),
            shapes="resources/user/shapes/{shape}.parquet",
            bathymetry=rules.download_bathymetry.output,
        output:
            "resources/automatic/cutout/{shape}/bathymetry.tif",
        log:
            "logs/{shape}/clip_bathymetry.log",
        conda:
            "../envs/default.yaml"
        message:
            "Cut bathymetry data to the bounds of the input shapefile."
        shell:
            """
            python {input.script:q} {input.bathymetry:q} {input.shapes:q} {output:q} 2>{log:q}
            """


##
# Globcover
##


rule download_globcover:
    output:
        "resources/automatic/global/globcover.zip",
    log:
        "logs/download_globcover.log",
    conda:
        "../envs/shell.yaml"
    params:
        url=internal["resources"]["automatic"]["globcover"],
    message:
        "Download the GlobCover land cover data (~380 MB)."
    shell:
        """
        curl -sSLo {output:q} {params.url:q}
        """


rule unzip_globcover:
    input:
        script=workflow.source_path("../scripts/unzip_like.py"),
        zipfile=rules.download_globcover.output,
    output:
        "resources/automatic/global/globcover-landcover.tif",
    log:
        "logs/unzip_globcover.log",
    conda:
        "../envs/shell.yaml"
    params:
        target_file=internal["resources"]["automatic"]["globcover_landcover_tif"],
    message:
        "Unzip the relevant TIF files from the GlobCover zip file."
    shell:
        """
        python {input.script:q} {input.zipfile:q} -f {params.target_file:q} -o {output:q} 2>{log:q}
        """


rule clip_landcover:
    input:
        script=workflow.source_path("../scripts/clip_raster.py"),
        shapes="resources/user/shapes/{shape}.parquet",
        landcover=rules.unzip_globcover.output,
    output:
        "resources/automatic/cutout/{shape}/landcover.tif",
    log:
        "logs/{shape}/clip_landcover.log",
    conda:
        "../envs/default.yaml"
    message:
        "Cut land cover data to the bounds of the input shapefile."
    shell:
        """
        python {input.script:q} {input.landcover:q} {input.shapes:q} {output:q} 2>{log:q}
        """


##
# Global Human Settlement Layer (GHSL)
##


rule download_ghsl:
    output:
        "resources/automatic/global/ghsl_built_s.zip",
    log:
        "logs/download_ghsl.log",
    conda:
        "../envs/shell.yaml"
    params:
        url=internal["resources"]["automatic"]["ghsl"],
    message:
        "Download the GHSL (Global Human Settlement Layer) built-up surface data."
    shell:
        """
        curl -sSLo {output:q} {params.url:q}
        """


rule unzip_ghsl:
    input:
        script=workflow.source_path("../scripts/unzip_like.py"),
        zipfile=rules.download_ghsl.output,
    output:
        "resources/automatic/global/ghsl_built_s.tif",
    log:
        "logs/unzip_ghsl.log",
    conda:
        "../envs/shell.yaml"
    params:
        target_file=internal["resources"]["automatic"]["ghsl_tif"],
    message:
        "Unzip the relevant TIF file from the GHSL data."
    shell:
        """
        python {input.script:q} {input.zipfile:q} -f {params.target_file:q} -o {output:q} 2>{log:q}
        """


rule clip_settlement:
    input:
        script=workflow.source_path("../scripts/clip_raster.py"),
        shapes="resources/user/shapes/{shape}.parquet",
        settlement=rules.unzip_ghsl.output,
    output:
        "resources/automatic/cutout/{shape}/settlement.tif",
    log:
        "logs/{shape}/clip_settlement.log",
    conda:
        "../envs/default.yaml"
    message:
        "Cut settlement data to the bounds of the input shapefile."
    shell:
        """
        python {input.script:q} {input.settlement:q} {input.shapes:q} {output:q} 2>{log:q}
        """


##
# Protected Areas (WDPA)
##


rule rasterise_clip_wdpa:
    input:
        script=workflow.source_path("../scripts/clip_and_rasterise_polys.py"),
        shapes="resources/user/shapes/{shape}.parquet",
        reference_raster=rules.clip_landcover.output,
        protected_areas="resources/user/wdpa.gdb",
    output:
        "resources/automatic/cutout/{shape}/wdpa.tif",
    log:
        "logs/{shape}/clip_wdpa.log",
    conda:
        "../envs/default.yaml"
    message:
        "Rasterise and cut WDPA data to the bounds of the input shapefile, using the landcover raster as reference for the rasterisation."
    shell:
        """
        python {input.script:q} {input.shapes:q} {input.reference_raster:q} {input.protected_areas:q} {output:q} 2>{log:q}
        """
