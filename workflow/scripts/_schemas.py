"""Schemas for tabular data used in the workflow."""

import pandera.pandas as pa
from pandera.typing.geopandas import GeoSeries
from pandera.typing.pandas import Series


class ShapesSchema(pa.DataFrameModel):
    """Schema for geographic shapes."""

    shape_id: Series[str] = pa.Field(unique=True)
    "A unique identifier for this shape."
    country_id: Series[str]
    "Country ISO alpha-3 code."
    shape_class: Series[str] = pa.Field(isin=["land", "maritime"])
    "Identifier of the shape's context."
    geometry: GeoSeries
    "Shape (multi)polygon."
    parent_name: Series[str] | None
    "Human-readable name in the parent dataset."

    @pa.check("geometry", element_wise=True)
    def check_geometries(cls, geom):
        return (geom is not None) and (not geom.is_empty) and geom.is_valid

    class Config:
        coerce = True
        strict = False
