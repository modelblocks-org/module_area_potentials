"""Utility functions."""

import math

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np


def random_categorical_cmap(n, base_cmap="tab20", seed=42):
    """Generate a random categorical colormap from a continuous base colormap.

    Parameters:
        n (int): Number of unique categories.
        base_cmap (str or Colormap): Name of the base matplotlib colormap or a Colormap object.
        seed (int, optional): Random seed for reproducibility.

    Returns:
        matplotlib.colors.ListedColormap: Colormap with `n` random colors.
    """
    if seed is not None:
        np.random.seed(seed)

    cmap = plt.get_cmap(base_cmap)
    # Sample `n` random values from [0, 1] and get corresponding colors
    colors = cmap(np.random.rand(n))
    return mcolors.ListedColormap(colors)


def plot_all_dataset_variables(ds, ncols=2, savefig=None, categorical_vars=[]):
    """Plot all variables in an xarray dataset on a grid of plots."""
    # Drop dimensionless variables
    ds = ds.drop_vars(lambda x: [v for v, da in x.variables.items() if not da.ndim])

    vars_to_plot = list(ds.data_vars)
    nrows = math.ceil(len(vars_to_plot) / ncols)

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(6 * ncols, 4 * nrows))
    axes = axes.flatten()

    for i, var in enumerate(vars_to_plot):
        if var in categorical_vars:
            cmap = random_categorical_cmap(len(ds[var].values))
        else:
            cmap = "viridis"
        ds[var].plot(ax=axes[i], cmap=cmap)
        axes[i].set_title(var)
        # We want to save rasterized images also for e.g. PDF output
        # Any actor with a zorder below the value given here is rasterized
        axes[i].set_rasterization_zorder(10000)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()

    if savefig:
        plt.savefig(savefig, dpi=300, bbox_inches="tight")

    return fig
