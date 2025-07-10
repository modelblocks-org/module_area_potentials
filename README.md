# Area potentials



A modular `snakemake` workflow built for [`clio`](https://clio.readthedocs.io/) data modules.

## Using this module

This module can be imported directly into any `snakemake` workflow.
Please consult the integration example in `tests/integration/Snakefile` for more information.

## Development

We use [`pixi`](https://pixi.sh/) as our package manager for development.
Once installed, run the following to clone this repo and install all dependencies.

```shell
git clone git@github.com:calliope-project/module_area_potentials.git
cd module_area_potentials
pixi install --all
```

For testing, simply run:

```shell
pixi run test
```

To view the documentation locally, use:

```shell
pixi run serve-docs
```

To test a minimal example of a workflow using this module:

```shell
pixi shell    # activate this project's environment
cd tests/integration/  # navigate to the integration example
snakemake --use-conda  # run the workflow!
```

## Data sources and licenses

* [GEDTM30](https://github.com/openlandmap/GEDTM30) for slope
    * License: Creative Commons Attribution 4.0 International
* [GlobCover land cover data](https://due.esrin.esa.int/page_globcover.php)
    * License: "You may use the GlobCover land cover map for educational and/or scientific purposes, without any fee on the condition that you credit ESA and the Université Catholique de Louvain as the source of the GlobCover products."
* [GEBCO (General Bathymetric Chart of the Oceans)](https://www.gebco.net/data-products/gridded-bathymetry-data) 15 arc-second data
    * License: "The GEBCO Grid is placed in the public domain and may be used free of charge. [...] Users must: Acknowledge the source of The GEBCO Grid. A suitable form of attribution is given in the documentation that accompanies The GEBCO Grid."
* [GHSL (Global Human Settlement Layer)](https://human-settlement.emergency.copernicus.eu/download.php) built-up surface data (R2023, GHS-BUILT-S, 100m resolution)
    * License: "The GHSL has been produced by the EC JRC as open and free data. Reuse is authorised, provided the source is acknowledged."
* [WDPA (World Database on Protected Areas)](https://www.protectedplanet.net/)
    * License: Non-commercial allowed. Citation: "UNEP-WCMC and IUCN (2025), Protected Planet: The World Database on Protected Areas (WDPA) and World Database on Other Effective Area-based Conservation Measures (WD-OECM) [Online], June 2025, Cambridge, UK: UNEP-WCMC and IUCN. Available at: www.protectedplanet.net."
