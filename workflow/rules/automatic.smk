"""Rules to used to download automatic resource files."""


rule download_cutout_slope:
    message:
        "Download slope data covering the bounds of the input shapefile."
    params:
        cog_url=internal["resources"]["automatic"]["slope"],
    input:
        vector="resources/user/shapes/{shape}.parquet",
    output:
        path="resources/automatic/cutout/{shape}/slope.tif",
    wrapper:
        "v7.2.0/geo/rasterio/clip-geotiff"


rule download_cutout_bathymetry:
    message:
        "Download bathymetry data covering the bounds of the input shapefile."
    params:
        cog_url=internal["resources"]["automatic"]["bathymetry"],
    input:
        vector="resources/user/shapes/{shape}.parquet",
    output:
        path="resources/automatic/cutout/{shape}/bathymetry.tif",
    wrapper:
        "v7.2.0/geo/rasterio/clip-geotiff"


rule download_globcover:
    message:
        "Download the GlobCover land cover data (~380 MB)."
    params:
        url=internal["resources"]["automatic"]["globcover"],
    output:
        "resources/automatic/global/globcover.zip",
    conda:
        "../envs/shell.yaml"
    shell:
        'curl -sSLo {output} "{params.url}"'


rule unzip_globcover:
    message:
        "Unzip the relevant TIF files from the GlobCover zip file."
    params:
        target_file=internal["resources"]["automatic"]["globcover_landcover_tif"],
    input:
        rules.download_globcover.output,
    output:
        "resources/automatic/global/globcover-landcover.tif",
    log:
        "logs/unzip_globcover.log",
    conda:
        "../envs/shell.yaml"
    shell:
        """
        temp_dir=$(mktemp -d)
        unzip -j {input} {params.target_file} -d $temp_dir
        mv $temp_dir/{params.target_file} {output}
        rm -R $temp_dir
        """


rule download_ghsl:
    message:
        "Download the GHSL (Global Human Settlement Layer) built-up surface data."
    params:
        url=internal["resources"]["automatic"]["ghsl"],
    output:
        "resources/automatic/global/ghsl_built_s.zip",
    conda:
        "../envs/shell.yaml"
    shell:
        'curl -sSLo {output} "{params.url}"'


rule unzip_ghsl:
    message:
        "Unzip the relevant TIF file from the GHSL data."
    params:
        target_file=internal["resources"]["automatic"]["ghsl_tif"],
    input:
        rules.download_ghsl.output,
    output:
        "resources/automatic/global/ghsl_built_s.tif",
    conda:
        "../envs/shell.yaml"
    shell:
        """
        temp_dir=$(mktemp -d)
        unzip -j {input} {params.target_file} -d $temp_dir
        mv $temp_dir/{params.target_file} {output}
        rm -R $temp_dir
        """
