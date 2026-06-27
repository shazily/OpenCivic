"""OData 4.0 CSDL $metadata XML stub for published datasets."""

from __future__ import annotations

import html

from app.db.models import Dataset


def build_odata_metadata_xml(dataset: Dataset, *, service_root: str) -> str:
    """Return minimal OData v4 CSDL metadata document for a dataset entity set."""
    entity_set = dataset.slug.replace("-", "_")
    namespace = "OpenCivic.Dataset"
    entity_type = f"{namespace}.{entity_set}"

    columns = (dataset.schema_snapshot or {}).get("columns", [])
    properties_xml = ""
    for column in columns:
        name = column.get("name")
        if not isinstance(name, str) or not name:
            continue
        odata_type = _odata_edm_type(column.get("type", "string"))
        safe_name = html.escape(name, quote=True)
        properties_xml += f'        <Property Name="{safe_name}" Type="{odata_type}"/>\n'

    if not properties_xml:
        properties_xml = '        <Property Name="id" Type="Edm.String"/>\n'

    return f"""<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="4.0" xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">
  <edmx:DataServices>
    <Schema Namespace="{namespace}" xmlns="http://docs.oasis-open.org/odata/ns/edm">
      <EntityType Name="{html.escape(entity_set, quote=True)}">
{properties_xml.rstrip()}
      </EntityType>
      <EntityContainer Name="DatasetContainer">
        <EntitySet Name="{html.escape(entity_set, quote=True)}" EntityType="{entity_type}"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""


def _odata_edm_type(column_type: object) -> str:
    mapping = {
        "integer": "Edm.Int64",
        "float": "Edm.Double",
        "boolean": "Edm.Boolean",
        "datetime": "Edm.DateTimeOffset",
        "date": "Edm.Date",
    }
    if isinstance(column_type, str):
        return mapping.get(column_type, "Edm.String")
    return "Edm.String"
