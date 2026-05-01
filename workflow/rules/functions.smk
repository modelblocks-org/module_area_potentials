def get_subunits(wildcards):
    checkpoint_output = checkpoints.breakup_shape.get(**wildcards).output[0]
    return expand(
        "<results>/{{shape}}/{subunit}/area_potential_{{tech}}.tif",
        subunit=glob_wildcards(
            os.path.join(checkpoint_output, "{subunit}.parquet")
        ).subunit,
    )
