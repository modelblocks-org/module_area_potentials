"""Rules to used to download automatic resource files."""

rule download_cutout_slope:
    message:
        "Download slope data covering the bounds of the input shapefile."
    params:
        cog_url=internal["resources"]["automatic"]["slope"],
    input:
        vector="resources/user/shapes.parquet",
    output:
        path="resources/cutout/slope.tif",
    wrapper:
        "https://github.com/irm-codebase/snakemake-wrappers/raw/rasterio-tiff-clipping/geo/rasterio/clip-geotiff"

rule download_cutout_bathymetry:
    message:
        "Download bathymetry data covering the bounds of the input shapefile."
    params:
        cog_url=internal["resources"]["automatic"]["bathymetry"],
    input:
        vector="resources/user/shapes.parquet",
    output:
        path="resources/cutout/bathymetry.tif",
    wrapper:
        "https://github.com/irm-codebase/snakemake-wrappers/raw/rasterio-tiff-clipping/geo/rasterio/clip-geotiff"

rule download_wdpa:
    message:
        "Download the WDPA (World Database on Protected Areas) data (~1.5 GB)."
    params:
        url=internal["resources"]["automatic"]["wdpa"],
    output:
        "resources/automatic/wdpa.zip",
    conda:
        "../envs/shell.yaml"
    shell:
        'curl -sSLo {output} "{params.url}"'

rule unzip_wdpa:
    message:
        "Unzip the WDPA (World Database on Protected Areas) data (~2.0 GB)."
    params:
        target=internal["resources"]["automatic"]["wdpa_gdb"],
    input:
        rules.download_wdpa.output,
    output:
        directory("resources/automatic/wdpa.gdb"),
    conda:
        "../envs/shell.yaml"
    shell:
        """
        temp_dir=$(mktemp -d)
        unzip {input} -d $temp_dir
        mv $temp_dir/{params.target} {output}
        rm -R $temp_dir
        """

rule download_globcover:
    message:
        "Download the GlobCover land cover data (~380 MB)."
    params:
        url=internal["resources"]["automatic"]["globcover"],
    output:
        "resources/automatic/globcover.zip",
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
        "resources/automatic/globcover-landcover.tif",
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
        "resources/automatic/ghsl_built_s.zip",
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
        "resources/automatic/ghsl_built_s.tif",
    conda:
        "../envs/shell.yaml"
    shell:
        """
        temp_dir=$(mktemp -d)
        unzip -j {input} {params.target_file} -d $temp_dir
        mv $temp_dir/{params.target_file} {output}
        rm -R $temp_dir
        """
