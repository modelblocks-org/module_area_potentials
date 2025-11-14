"""Schemas for tabular data used in the workflow."""

from pandera.pandas import DataFrameModel, Field, check
from pandera.typing.geopandas import GeoSeries
from pandera.typing.pandas import Series
from shapely.geometry import Point


class Shapes(DataFrameModel):
    class Config:
        coerce = True
        strict = False

    shape_id: Series[str] = Field(unique=True)
    "Unique ID for this shape."
    country_id: Series[str]
    "ISO alpha-3 code."
    shape_class: Series[str] = Field(isin=["land", "maritime"])
    "Shape classifier"
    geometry: GeoSeries[Point] = Field()
    "Shape polygon."

    @check("geometry", element_wise=True)
    def geom_not_empty(cls, geom):
        return (geom is not None) and (not geom.is_empty) and geom.is_valid
