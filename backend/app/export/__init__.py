"""Cozmo Stage 4 property export package.

Purpose:
    Exposes unified export generators for JSON, SVG, PDF, and DXF deliverables
    derived directly from backend reconstruction artifacts with strict capture isolation.

Stage:
    Frontend Stage 4 — Exports + Final Product Polish.

Deliverables:
    - export_property_json: Machine-readable JSON with honest confidence intervals.
    - export_property_svg: Standalone vector floor plan SVG with readable dimensions.
    - export_property_pdf: Multi-page engineering & inspection PDF report.
    - export_property_dxf: Metric CAD-compatible 2D DXF floor plan with layers.
    - export_all_formats: Orchestrates generation of all four deliverables into an isolated export directory.

Dependencies:
    .json_export, .svg_export, .pdf_export, .dxf_export.

Assumptions:
    Export inputs originate directly from current capture reconstruction outputs.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel

from .json_export import export_property_json
from .svg_export import export_property_svg
from .pdf_export import export_property_pdf
from .dxf_export import export_property_dxf


def export_all_formats(
    property_data: Union[Dict[str, Any], BaseModel],
    capture_id: str,
    output_dir: Path,
) -> Dict[str, Path]:
    """Generates all four export deliverables (JSON, SVG, PDF, DXF) into an isolated directory.

    Purpose:
        Single entry point for pre-generating or batch-exporting all deliverables
        for a completed capture into ``runtime/captures/<id>/exports/``.

    Parameters:
        property_data: Property reconstruction data.
        capture_id: Unique capture identifier.
        output_dir: Destination directory Path for export files.

    Returns:
        Dict mapping format keys ('json', 'svg', 'pdf', 'dxf') to their created file Paths.

    Units / Coordinates:
        Metric units preserved consistently across all formats.

    Debugging Clues:
        Check that all 4 returned Paths exist and have non-zero file sizes.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"cozmo_{capture_id}_property.json"
    svg_path = out_dir / f"cozmo_{capture_id}_floorplan.svg"
    pdf_path = out_dir / f"cozmo_{capture_id}_report.pdf"
    dxf_path = out_dir / f"cozmo_{capture_id}_floorplan.dxf"

    export_property_json(property_data, capture_id, output_path=json_path)
    export_property_svg(property_data, capture_id, output_path=svg_path)
    export_property_pdf(property_data, capture_id, output_path=pdf_path)
    export_property_dxf(property_data, capture_id, output_path=dxf_path)

    return {
        "json": json_path,
        "svg": svg_path,
        "pdf": pdf_path,
        "dxf": dxf_path,
    }


__all__ = [
    "export_property_json",
    "export_property_svg",
    "export_property_pdf",
    "export_property_dxf",
    "export_all_formats",
]
