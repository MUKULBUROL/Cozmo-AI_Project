"""Machine-readable JSON property exporter complying with Cozmo Stage 4 deliverable contracts.

Purpose:
    Serializes reconstructed property geometry, metric dimensions, confidence
    intervals, detected openings, damage regions, repair scopes, and whole-property
    topology into standardized, machine-readable JSON format.

Stage:
    Frontend Stage 4 — Exports + Final Product Polish.

Inputs:
    - property_data: Dict or PropertyPlanOutput object representing reconstruction results.
    - capture_id: Unique capture identifier string.
    - output_path: Optional destination Path for writing the JSON file.

Outputs:
    - JSON string or written file containing full property data structure.
    - Preserves nulls, NOT_EVALUABLE, and PROVISIONAL states honestly.

Dependencies:
    json, pathlib, typing, pydantic (if PropertyPlanOutput model passed).

Assumptions:
    - Distance measurements are in metric meters (m).
    - Area measurements are in square meters (m2).
    - Angles are in degrees.
    - Missing or unmeasured fields remain null/None without fabricated defaults.

Coordinate / Unit Conventions:
    - Ground plane: Global horizontal (X, Z) in meters.
    - Vertical axis: Y upward in meters.

Failure Modes:
    - Unserializable data types in input dictionary -> caught and serialized safely.
    - Write permission failure -> raises IOError with descriptive path.

First Debugging Points:
    - Check output file existence and JSON syntax validity (`json.loads`).
    - Verify capture_id matches the active capture.
    - Ensure confidence intervals [lower_bound, upper_bound] are present.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel


def export_property_json(
    property_data: Union[Dict[str, Any], BaseModel],
    capture_id: str,
    output_path: Optional[Path] = None,
    indent: int = 2,
) -> str:
    """Serializes property reconstruction data to standard JSON format.

    Purpose:
        Produces a complete, machine-readable JSON artifact representing the
        entire reconstructed property, preserving honest confidence intervals
        and status values.

    Parameters:
        property_data: Property reconstruction data as a dictionary or Pydantic model.
        capture_id: Unique capture ID string for provenance tracking.
        output_path: Optional Path to write the JSON file to.
        indent: JSON indentation spaces (default 2).

    Returns:
        Formatted JSON string.

    Units / Coordinates:
        All dimensions in meters (m), areas in square meters (m2).

    Assumptions:
        property_data reflects actual backend reconstruction output.

    Failure Conditions:
        Raises IOError if writing to output_path fails.

    Debugging Clues:
        Check json.loads() on returned string; verify 'capture_id' key matches.
    """
    if isinstance(property_data, BaseModel):
        data = property_data.model_dump(mode="json")
    elif isinstance(property_data, dict):
        data = dict(property_data)
    else:
        raise TypeError(f"Expected dict or BaseModel, got {type(property_data)}")

    # Ensure capture_id and property_id are stamped accurately
    data["capture_id"] = capture_id
    if "property_id" not in data or not data["property_id"]:
        data["property_id"] = capture_id

    # Format into indented JSON
    json_text = json.dumps(data, indent=indent, default=str)

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json_text, encoding="utf-8")

    return json_text
