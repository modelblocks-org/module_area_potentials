BASE_DIR = workflow.basedir

wildcard_constraints:
    tech="|".join(config["techs"].keys())

rule slope_too_steep:
    message:
        "Get areas with slope values greater than max_slope, i.e. too steep/not suitable for the tech {wildcards.tech}.",
    params:
        max_slope=lambda wildcards: config["techs"][f"{wildcards.tech}"]["max_slope"]
    input:
        shapes=rules.cutout_slope.output,
    output:
        "resources/slope_too_steep_{tech}.nc",
    conda:
        "../envs/default.yaml"
    shell:
        "python {BASE_DIR}/scripts/get_slope_too_steep.py {input} {params.max_slope} {output}"
