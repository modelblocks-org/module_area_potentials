"""Utility functions."""

import math

import matplotlib.pyplot as plt


def plot_all_dataset_variables(ds, ncols=2, savefig=None):
    """Plot all variables in an xarray dataset on a grid of plots."""
    # Drop dimensionless variables
    ds = ds.drop_vars(lambda x: [v for v, da in x.variables.items() if not da.ndim])

    vars_to_plot = list(ds.data_vars)
    nrows = math.ceil(len(vars_to_plot) / ncols)

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(6 * ncols, 4 * nrows))
    axes = axes.flatten()

    for i, var in enumerate(vars_to_plot):
        ds[var].plot(ax=axes[i])
        axes[i].set_title(var)
        # We want to save rasterized images also for e.g. PDF output
        # Any actor with a zorder below the value given here is rasterized
        axes[i].set_rasterization_zorder(10000)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()

    if savefig:
        plt.savefig(savefig, bbox_inches="tight")

    return fig
