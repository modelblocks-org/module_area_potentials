"""Rules to used to download automatic resource files."""

if config.get("tiny_files", False):

    ##
    # Directly download clipped slope and bathymetry data
    ##

    rule clip_slope:
        input:
            like_vector=rules.normalise_shapes.output.shapes,
        output:
            path="<resources>/automatic/cutout/{shape}/slope.tif",
        log:
            "<logs>/{shape}/clip_slope.log",
        localrule: True
        params:
            cog_url=internal["resources"]["automatic"]["slope"],
        message:
            "Download slope data covering the bounds of the input shapefile."
        wrapper:
            "v9.14.0/geo/rasterio/clip"

    rule clip_bathymetry:
        input:
            like_vector=rules.normalise_shapes.output.shapes,
        output:
            path="<resources>/automatic/cutout/{shape}/bathymetry.tif",
        log:
            "<logs>/{shape}/clip_bathymetry.log",
        localrule: True
        params:
            cog_url=internal["resources"]["automatic"]["bathymetry"],
        message:
            "Download bathymetry data covering the bounds of the input shapefile."
        wrapper:
            "v9.14.0/geo/rasterio/clip"

else:

    ##
    # Download global slope and bathymetry data, then clip the files locally
    ##

    rule download_slope:
        output:
            path="<resources>/automatic/global/slope.tif",
        log:
            "<logs>/download_slope.log",
        localrule: True
        conda:
            "../envs/module.yaml"
        params:
            url=internal["resources"]["automatic"]["slope"],
        message:
            "Download global slope data."
        shell:
            """
            curl -sSLo {output:q} {params.url:q} >{log:q} 2>&1
            """

    rule download_bathymetry:
        output:
            path="<resources>/automatic/global/bathymetry.tif",
        log:
            "<logs>/download_bathymetry.log",
        localrule: True
        conda:
            "../envs/module.yaml"
        params:
            url=internal["resources"]["automatic"]["bathymetry"],
        message:
            "Download global bathymetry data."
        shell:
            """
            curl -sSLo {output:q} {params.url:q} >{log:q} 2>&1
            """

    rule clip_slope:
        input:
            like_vector=rules.normalise_shapes.output.shapes,
            raster=rules.download_slope.output[0],
        output:
            path="<resources>/automatic/cutout/{shape}/slope.tif",
        log:
            "<logs>/{shape}/clip_slope.log",
        message:
            "Cut slope data to the bounds of the input shapefile."
        wrapper:
            "v9.14.0/geo/rasterio/clip"

    rule clip_bathymetry:
        input:
            like_vector=rules.normalise_shapes.output.shapes,
            raster=rules.download_bathymetry.output[0],
        output:
            path="<resources>/automatic/cutout/{shape}/bathymetry.tif",
        log:
            "<logs>/{shape}/clip_bathymetry.log",
        message:
            "Cut bathymetry data to the bounds of the input shapefile."
        wrapper:
            "v9.14.0/geo/rasterio/clip"


##
# Globcover
##


rule download_globcover:
    output:
        "<resources>/automatic/global/globcover.zip",
    log:
        "<logs>/download_globcover.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    params:
        url=internal["resources"]["automatic"]["globcover"],
    message:
        "Download the GlobCover land cover data (~380 MB)."
    shell:
        """
        curl -sSLo {output:q} {params.url:q} >{log:q} 2>&1
        """


rule unzip_globcover:
    input:
        script=workflow.source_path("../scripts/unzip_like.py"),
        zipfile=rules.download_globcover.output,
    output:
        "<resources>/automatic/global/globcover-landcover.tif",
    log:
        "<logs>/unzip_globcover.log",
    conda:
        "../envs/module.yaml"
    params:
        target_file=internal["resources"]["automatic"]["globcover_landcover_tif"],
    message:
        "Unzip the relevant TIF files from the GlobCover zip file."
    shell:
        """
        python {input.script:q} {input.zipfile:q} -f {params.target_file:q} -o {output:q} >{log:q} 2>&1
        """


rule clip_landcover:
    input:
        like_vector=rules.normalise_shapes.output.shapes,
        raster=rules.unzip_globcover.output[0],
    output:
        path="<resources>/automatic/cutout/{shape}/landcover.tif",
    log:
        "<logs>/{shape}/clip_landcover.log",
    message:
        "Cut land cover data to the bounds of the input shapefile."
    wrapper:
        "v9.14.0/geo/rasterio/clip"


##
# Global Ship Traffic Density
##


rule download_ship_travel:
    output:
        "<resources>/automatic/global/ship_travel_density.zip",
    log:
        "<logs>/download_ship_travel.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    params:
        url=internal["resources"]["automatic"]["ship_travel"],
    message:
        "Download Global Ship Density for all vessel types."
    shell:
        """
        curl -sSLo {output:q} {params.url:q} >{log:q} 2>&1
        """


rule unzip_ship_travel:
    input:
        rules.download_ship_travel.output[0],
    output:
        temp("<resources>/automatic/global/ship_travel.tif"),
    log:
        "<logs>/unzip_ship_travel.log",
    params:
        internal_paths=internal["resources"]["automatic"]["ship_travel_tif"],
    message:
        "Unzip the relevant TIF file from the ship travel density data."
    wrapper:
        "v9.8.0/utils/libarchive/extract"


rule clip_ship_travel:
    input:
        like_vector=rules.normalise_shapes.output.shapes,
        raster=rules.unzip_ship_travel.output[0],
    output:
        path="<resources>/automatic/cutout/{shape}/ship_travel.tif",
    log:
        "<logs>/{shape}/clip_ship_travel.log",
    message:
        "Cut ship travel data to the bounds of the input shapefile."
    wrapper:
        "v9.14.0/geo/rasterio/clip"


##
# Global Human Settlement Layer (GHSL)
##


rule download_ghsl:
    output:
        "<resources>/automatic/global/ghsl_built_s.zip",
    log:
        "<logs>/download_ghsl.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    params:
        url=internal["resources"]["automatic"]["ghsl"],
    message:
        "Download the GHSL (Global Human Settlement Layer) built-up surface data."
    shell:
        """
        curl -sSLo {output:q} {params.url:q} >{log:q} 2>&1
        """


rule unzip_ghsl:
    input:
        script=workflow.source_path("../scripts/unzip_like.py"),
        zipfile=rules.download_ghsl.output,
    output:
        "<resources>/automatic/global/ghsl_built_s.tif",
    log:
        "<logs>/unzip_ghsl.log",
    conda:
        "../envs/module.yaml"
    params:
        target_file=internal["resources"]["automatic"]["ghsl_tif"],
    message:
        "Unzip the relevant TIF file from the GHSL data."
    shell:
        """
        python {input.script:q} {input.zipfile:q} -f {params.target_file:q} -o {output:q} >{log:q} 2>&1
        """


rule clip_settlement:
    input:
        like_vector=rules.normalise_shapes.output.shapes,
        raster=rules.unzip_ghsl.output[0],
    output:
        path="<resources>/automatic/cutout/{shape}/settlement.tif",
    log:
        "<logs>/{shape}/clip_settlement.log",
    message:
        "Cut settlement data to the bounds of the input shapefile."
    wrapper:
        "v9.14.0/geo/rasterio/clip"


##
# Protected Areas (WDPA)
##


rule rasterise_clip_wdpa:
    input:
        script=workflow.source_path("../scripts/clip_and_rasterise_polys.py"),
        shapes=rules.normalise_shapes.output.shapes,
        reference_raster=rules.clip_landcover.output[0],
        protected_areas="<wdpa>",
    output:
        "<resources>/automatic/cutout/{shape}/wdpa.tif",
    log:
        "<logs>/{shape}/clip_wdpa.log",
    benchmark:
        "<logs>/{shape}/clip_wdpa.benchmark.tsv"
    conda:
        "../envs/module.yaml"
    resources:
        mem_mb=3000,
    message:
        "Rasterise and cut WDPA data to the bounds of the input shapefile, using the landcover raster as reference for the rasterisation."
    shell:
        """
        python {input.script:q} {input.shapes:q} {input.reference_raster:q} {input.protected_areas:q} {output:q} >{log:q} 2>&1
        """
