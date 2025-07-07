import pandas as pd
import xarray as xr


def report(area_potentials, csv_path, html_path):
    report_values = []
    for area_potential in area_potentials:
        ds = xr.open_dataset(area_potential)
        val = ds.squeeze().sum().to_dataarray().values[0] / (1e6)  # Convert to km²
        report_values.append((area_potential, val))
        # report += f"Area potential for {area_potential}: {val:.2f} km²\n"
    # with open(report_path, "w") as f:
    #     f.write(report)
    df = pd.DataFrame(report_values, columns=["Area Potential", "Value (km²)"])
    df.to_csv(csv_path, index=False)
    df.to_html(html_path, index=False)


if __name__ == "__main__":
    report(snakemake.input.area_potentials, snakemake.output.csv, snakemake.output.html)
