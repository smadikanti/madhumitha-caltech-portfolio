"""Data export in CSV, JSON, and VOTable formats."""

import csv
import io
import json
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from archive_api.database import get_db
from archive_api.models import Exoplanet
from archive_api.schemas import ExportFormat

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_EXPORT_FIELDS = [
    "pl_name",
    "hostname",
    "discovery_method",
    "disc_year",
    "orbital_period",
    "pl_rade",
    "pl_bmasse",
    "pl_eqt",
    "st_teff",
    "st_rad",
    "sy_dist",
    "ra",
    "dec",
]


@router.get("", summary="Export the full catalog in CSV, JSON, or VOTable")
async def export_data(
    format: ExportFormat = Query(ExportFormat.csv, description="Output format"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Stream the entire catalog in the requested serialization format."""
    rows = (await db.execute(select(Exoplanet))).scalars().all()
    records = [{f: getattr(r, f) for f in _EXPORT_FIELDS} for r in rows]

    if format == ExportFormat.csv:
        return _csv_response(records)
    if format == ExportFormat.json:
        return _json_response(records)
    return _votable_response(records)


def _csv_response(records: list[dict]) -> Response:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_EXPORT_FIELDS)
    writer.writeheader()
    writer.writerows(records)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=exoplanets.csv"},
    )


def _json_response(records: list[dict]) -> Response:
    return Response(
        content=json.dumps(records, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=exoplanets.json"},
    )


# ---- VOTable (IVOA standard for tabular astronomy data) ------------------

_VOTABLE_FIELDS: dict[str, tuple[str, str, str]] = {
    "pl_name": ("char", "*", "Planet Name"),
    "hostname": ("char", "*", "Host Star Name"),
    "discovery_method": ("char", "*", "Discovery Method"),
    "disc_year": ("int", "", "Discovery Year"),
    "orbital_period": ("double", "", "Orbital Period [days]"),
    "pl_rade": ("double", "", "Planet Radius [Earth radii]"),
    "pl_bmasse": ("double", "", "Planet Mass [Earth masses]"),
    "pl_eqt": ("double", "", "Equilibrium Temperature [K]"),
    "st_teff": ("double", "", "Stellar Effective Temperature [K]"),
    "st_rad": ("double", "", "Stellar Radius [Solar radii]"),
    "sy_dist": ("double", "", "Distance [pc]"),
    "ra": ("double", "", "Right Ascension [deg]"),
    "dec": ("double", "", "Declination [deg]"),
}


def _votable_response(records: list[dict]) -> Response:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.4">',
        '  <RESOURCE name="exoplanet_archive">',
        '    <TABLE name="ps">',
    ]

    for name, (datatype, arraysize, description) in _VOTABLE_FIELDS.items():
        arr = f' arraysize="{arraysize}"' if arraysize else ""
        lines.append(
            f'      <FIELD name="{name}" datatype="{datatype}"{arr}'
            f' description="{xml_escape(description)}"/>'
        )

    lines.append("      <DATA>")
    lines.append("        <TABLEDATA>")

    for rec in records:
        cells = "".join(
            f"<TD>{xml_escape(str(rec[f])) if rec[f] is not None else ''}</TD>"
            for f in _VOTABLE_FIELDS
        )
        lines.append(f"          <TR>{cells}</TR>")

    lines.extend([
        "        </TABLEDATA>",
        "      </DATA>",
        "    </TABLE>",
        "  </RESOURCE>",
        "</VOTABLE>",
    ])

    return Response(
        content="\n".join(lines),
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=exoplanets.xml"},
    )
