"""Rules to used to download automatic resource files."""

rule download_cutout_slope:
    message:
        "Download slope data covering the bounds of the input shapefile."
    params:
        tiff_url=internal["resources"]["automatic"]["slope"],
    input:
        vector="resources/user/shapes.parquet",
    output:
        path="resources/automatic/slope_cutout.tif",
    wrapper:
        "https://github.com/irm-codebase/snakemake-wrappers/raw/rasterio-tiff-clipping/geo/rasterio/clip-cog"

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
        target_file_1=internal["resources"]["automatic"]["globcover_landcover_tif"],
        target_file_2=internal["resources"]["automatic"]["globcover_landseamask_tif"],
    input:
        rules.download_globcover.output,
    output:
        landcover="resources/automatic/globcover-landcover.tif",
        landseamask="resources/automatic/globcover-landseamask.tif",
    log:
        "logs/unzip_globcover.log",
    conda:
        "../envs/shell.yaml"
    shell:
        """
        temp_dir=$(mktemp -d)
        unzip -j {input} {params.target_file_1} -d $temp_dir
        unzip -j {input} {params.target_file_2} -d $temp_dir
        mv $temp_dir/{params.target_file_1} {output.landcover}
        mv $temp_dir/{params.target_file_2} {output.landseamask}
        rm -R $temp_dir
        """

rule download_ghsl:
    message:
        "Download the GHSL (Global Human Settlement Layer) built-up surface data (R2023, GHS-BUILT-S, 100m resolution, ~2 GB)."
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

rule download_gebco:
    message:
        "Download the GEBCO (General Bathymetric Chart of the Oceans) 15 arc-second data (4 GB zipped, 8 GB unzipped)."
    params:
        url=internal["resources"]["automatic"]["gebco"],
    output:
        "resources/automatic/gebco_2024_sub_ice_topo_geotiff.zip",
    conda:
        "../envs/shell.yaml"
    shell:
        'curl -sSLo {output} "{params.url}"'

rule unzip_gebco:
    message:
        "Unzip all (TIF) files from the GEBCO data."
    input:
        rules.download_gebco.output,
    output:
        directory("resources/automatic/gebco"),
    conda:
        "../envs/shell.yaml"
    shell:
        """
        unzip -j {input} -d {output}
        """

rule merge_gebco:
    message:
        "Merge all GEBCO TIF files into a single TIF file."
    input:
        rules.unzip_gebco.output
    output:
        "resources/automatic/gebco.tif",
    conda:
        "../envs/shell.yaml"
    shell:
        """
        rio merge {input}/gebco_2024_sub_ice_*.tif {output} --overwrite
        """
