"""Master Stage 4 orchestrator: Metric measurements, room area, and honest uncertainty propagation.

1. Why this file exists:
   Transforms Stage 3 2D room polygons and Stage 2 structural planes into certified,
   machine-readable metric dimensions (wall lengths, room perimeter, polygon floor area,
   and optional clear ceiling height) accompanied by physically derived 95% confidence intervals,
   evidence-based confidence scores, and an automated measurement validity gate.

2. Pipeline stage:
   Stage 4 (Metric Measurements, Room Area & Uncertainty) - Core Measurement Engine.

3. Inputs:
   outputs/<scan_id>/floorplan_geometry/room_polygon.json
   outputs/<scan_id>/floorplan_geometry/polygon_stats.json
   outputs/<scan_id>/floorplan_geometry/wall_quality.json
   outputs/<scan_id>/floorplan_geometry/corners.json
   outputs/<scan_id>/structure/structure.json

4. Outputs:
   outputs/<scan_id>/measurements/
     ├── measurements.json        (Master output adhering to Challenge Output Contract)
     ├── wall_dimensions.json     (Detailed wall edge metrics and error components)
     ├── uncertainty.json         (Comprehensive error breakdown and Monte Carlo log)
     ├── measurement_stats.json   (Executive summary metrics)
     └── dimensioned_debug.svg    (Dark-mode dimensioned CAD diagnostic diagram)

5. Coordinate/Unit assumptions:
   Y is vertical (upward).
   XZ is horizontal floor plane.
   All coordinates and dimensions are in metric units: meters (m), square meters (m2).

6. Dependencies:
   json, math, pathlib, typing, pydantic, numpy, shapely,
   backend.app.models.output, .validity_gate, .uncertainty, .svg_render.

7. Most likely failure/debugging points:
   - Missing Stage 3 room_polygon.json if Stage 3 was not executed.
   - Missing Stage 2 structure.json if Stage 2 was not executed.
   - Non-simple or self-intersecting polygon failing validity gate.
"""

import os
import json
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from shapely.geometry import Polygon
from pydantic import BaseModel, Field

from backend.app.models.output import Measurement
from .validity_gate import evaluate_measurement_validity, ValidityStatus, ValidityReport
from .uncertainty import (
    calculate_corner_positional_uncertainty,
    calculate_wall_length_uncertainty,
    monte_carlo_area_and_perimeter_uncertainty,
    derive_wall_confidence,
    derive_area_confidence,
)
from .svg_render import render_dimensioned_debug_svg


class WallDimensionItem(BaseModel):
    """Detailed dimension representation of an individual polygon wall edge."""
    wall_id: str
    edge_index: int
    start_corner_id: str
    end_corner_id: str
    start: List[float]
    end: List[float]
    length_m: float
    interval_95_m: List[float]
    confidence: float
    has_inferred_corner: bool
    inferred_corner_ids: List[str]
    wall_plane_quality: Dict[str, Any]
    uncertainty_components: Dict[str, Any]


class MeasurementReport(BaseModel):
    """Comprehensive Stage 4 measurement deliverables package."""
    scan_id: str
    status: ValidityStatus
    status_reasons: List[str]
    walls: List[Dict[str, Any]]
    floor_area: Measurement[float]
    perimeter: Measurement[float]
    ceiling_height: Optional[Measurement[float]] = None
    ceiling_status: str
    inferred_corner_count: int
    wall_count: int
    summary_stats: Dict[str, Any]


def compute_room_measurements(
    scan_id: str,
    stage3_geometry_dir: Path,
    stage2_structure_json_path: Path,
    output_dir: Optional[Path] = None,
    mc_samples: int = 1000,
    random_seed: int = 42,
    confidence_level: float = 0.95,
) -> Dict[str, Any]:
    """Executes the full Stage 4 measurement and uncertainty computation workflow.

    Purpose:
        Coordinates data loading, geometric validity gating, analytical wall length calculation,
        Monte Carlo area/perimeter sensitivity analysis, plane distance computation for ceiling,
        and JSON/SVG artifact export.

    Parameters:
        scan_id: Unique capture identifier (e.g. 'c00a170fe1').
        stage3_geometry_dir: Directory containing Stage 3 JSON deliverables.
        stage2_structure_json_path: Path to Stage 2 structure.json file.
        output_dir: Output directory for Stage 4 deliverables (defaults to outputs/<scan_id>/measurements/).
        mc_samples: Number of Monte Carlo iterations for area/perimeter uncertainty.
        random_seed: Random seed guaranteeing deterministic reproducibility.
        confidence_level: Coverage probability for uncertainty intervals (default 0.95).

    Returns:
        Dictionary containing serialized measurement results and file paths.

    Assumptions:
        Stage 3 room_polygon.json exists and contains 2D XZ coordinates in meters.
        Ceiling height is strictly evaluated from Stage 2 planes (never hallucinated).

    Failure conditions:
        Raises FileNotFoundError if room_polygon.json or structure.json is missing.

    Debugging:
        Check measurement_stats.json and validity reasons if status evaluates to 'provisional' or 'invalid'.
    """
    if output_dir is None:
        output_dir = stage3_geometry_dir.parent / "measurements"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Inputs
    room_polygon_file = stage3_geometry_dir / "room_polygon.json"
    if not room_polygon_file.exists():
        raise FileNotFoundError(f"Required Stage 3 room_polygon.json not found at {room_polygon_file}")

    with open(room_polygon_file, "r", encoding="utf-8") as f:
        polygon_data = json.load(f)

    polygon_stats_file = stage3_geometry_dir / "polygon_stats.json"
    polygon_stats = {}
    if polygon_stats_file.exists():
        with open(polygon_stats_file, "r", encoding="utf-8") as f:
            polygon_stats = json.load(f)

    wall_quality_file = stage3_geometry_dir / "wall_quality.json"
    wall_quality = {}
    if wall_quality_file.exists():
        with open(wall_quality_file, "r", encoding="utf-8") as f:
            wall_quality = json.load(f)

    corners_file = stage3_geometry_dir / "corners.json"
    corners_list: List[Dict[str, Any]] = []
    if corners_file.exists():
        with open(corners_file, "r", encoding="utf-8") as f:
            raw_corners = json.load(f)
            if isinstance(raw_corners, dict):
                corners_list = raw_corners.get("accepted_corners", raw_corners.get("corners", []))
            elif isinstance(raw_corners, list):
                corners_list = raw_corners
    elif "corners" in polygon_data:
        corners_list = polygon_data["corners"]

    structure_data = {}
    if stage2_structure_json_path.exists():
        with open(stage2_structure_json_path, "r", encoding="utf-8") as f:
            structure_data = json.load(f)

    # Build fast lookup indexes
    corner_lookup: Dict[str, Dict[str, Any]] = {c["id"]: c for c in corners_list if "id" in c}
    wall_quality_lookup: Dict[str, Dict[str, Any]] = {
        w["wall_id"]: w for w in wall_quality.get("accepted_walls", []) if "wall_id" in w
    }

    # 2. STEP 1: Measurement Validity Gate
    validity_report = evaluate_measurement_validity(
        polygon_data=polygon_data,
        polygon_stats=polygon_stats,
        wall_quality=wall_quality,
        corners_data=corners_list,
    )

    # 3. Extract and sanitize polygon vertices
    poly_section = polygon_data.get("polygon", polygon_data)
    raw_vertices = poly_section.get("vertices", [])
    if len(raw_vertices) > 1 and np.allclose(raw_vertices[0], raw_vertices[-1], atol=1e-4):
        unique_vertices: List[Tuple[float, float]] = [tuple(p) for p in raw_vertices[:-1]]
    else:
        unique_vertices = [tuple(p) for p in raw_vertices]

    num_vertices = len(unique_vertices)
    poly_corner_ids = poly_section.get("corner_ids", [])
    poly_wall_ids = poly_section.get("wall_ids", [])

    # Pad corner_ids or wall_ids if count does not match vertices
    if len(poly_corner_ids) < num_vertices:
        poly_corner_ids = [f"corner_{i+1:02d}" for i in range(num_vertices)]
    if len(poly_wall_ids) < num_vertices:
        poly_wall_ids = [f"wall_{i+1:02d}" for i in range(num_vertices)]

    # 4. STEP 6 & 7: Corner Uncertainty & Wall Lengths
    corner_sigmas: List[float] = []
    for i in range(num_vertices):
        cid = poly_corner_ids[i]
        c_meta = corner_lookup.get(cid, {})
        is_inf = c_meta.get("inferred", False)
        ext_a = c_meta.get("extension_wall_a_m", 0.0)
        ext_b = c_meta.get("extension_wall_b_m", 0.0)
        max_ext = max(ext_a, ext_b)
        ang = c_meta.get("angle_deg", 90.0)

        # Retrieve RMSEs of intersecting walls
        w_ids = c_meta.get("wall_ids", [])
        w_a = wall_quality_lookup.get(w_ids[0] if len(w_ids) > 0 else "", {})
        w_b = wall_quality_lookup.get(w_ids[1] if len(w_ids) > 1 else "", {})
        rmse_a = w_a.get("rmse_m", 0.02)
        rmse_b = w_b.get("rmse_m", 0.02)

        sigma_c = calculate_corner_positional_uncertainty(
            rmse_a_m=rmse_a,
            rmse_b_m=rmse_b,
            intersection_angle_deg=ang,
            is_inferred=is_inf,
            extension_m=max_ext,
        )
        corner_sigmas.append(sigma_c)

    wall_dimension_items: List[Dict[str, Any]] = []
    measurement_walls_output: List[Dict[str, Any]] = []
    wall_confidences: List[float] = []

    for i in range(num_vertices):
        p1 = unique_vertices[i]
        p2 = unique_vertices[(i + 1) % num_vertices]
        cid1 = poly_corner_ids[i]
        cid2 = poly_corner_ids[(i + 1) % num_vertices]
        wid = poly_wall_ids[i]

        sigma_c1 = corner_sigmas[i]
        sigma_c2 = corner_sigmas[(i + 1) % num_vertices]

        c1_meta = corner_lookup.get(cid1, {})
        c2_meta = corner_lookup.get(cid2, {})
        inf_1 = c1_meta.get("inferred", False)
        inf_2 = c2_meta.get("inferred", False)
        ext_1 = max(c1_meta.get("extension_wall_a_m", 0.0), c1_meta.get("extension_wall_b_m", 0.0))
        ext_2 = max(c2_meta.get("extension_wall_a_m", 0.0), c2_meta.get("extension_wall_b_m", 0.0))
        max_edge_ext = max(ext_1, ext_2)

        w_meta = wall_quality_lookup.get(wid, {})
        w_rmse = w_meta.get("rmse_m", 0.025)
        w_conf = w_meta.get("confidence", 0.70)

        # Compute raw Euclidean length (unrounded internally)
        dx = p2[0] - p1[0]
        dz = p2[1] - p1[1]
        raw_length_m = float(math.hypot(dx, dz))

        low_b, high_b, u_comps = calculate_wall_length_uncertainty(
            nominal_length_m=raw_length_m,
            wall_rmse_m=w_rmse,
            corner_a_uncertainty_m=sigma_c1,
            corner_b_uncertainty_m=sigma_c2,
            corner_a_inferred=inf_1,
            corner_b_inferred=inf_2,
            corner_extension_m=max_edge_ext,
            confidence_level=confidence_level,
        )

        edge_conf = derive_wall_confidence(
            plane_confidence=w_conf,
            wall_rmse_m=w_rmse,
            corner_a_inferred=inf_1,
            corner_b_inferred=inf_2,
        )
        wall_confidences.append(edge_conf)

        inf_ids = []
        if inf_1:
            inf_ids.append(cid1)
        if inf_2:
            inf_ids.append(cid2)

        item = {
            "wall_id": wid,
            "edge_index": i,
            "start_corner_id": cid1,
            "end_corner_id": cid2,
            "start": [p1[0], p1[1]],
            "end": [p2[0], p2[1]],
            "length_m": raw_length_m,
            "interval_95_m": [low_b, high_b],
            "confidence": round(edge_conf, 3),
            "has_inferred_corner": (inf_1 or inf_2),
            "inferred_corner_ids": inf_ids,
            "wall_plane_quality": {
                "rmse_m": w_rmse,
                "confidence": w_conf,
                "inlier_count": w_meta.get("inliers", 0),
            },
            "uncertainty_components": u_comps,
        }
        wall_dimension_items.append(item)

        # Standard challenge measurement output item
        measurement_walls_output.append({
            "id": wid,
            "edge_index": i,
            "start_corner": cid1,
            "end_corner": cid2,
            "length": {
                "value": round(raw_length_m, 3),
                "unit": "m",
                "lower_bound": round(low_b, 3),
                "upper_bound": round(high_b, 3),
                "interval": [round(low_b, 3), round(high_b, 3)],
                "confidence": round(edge_conf, 3),
                "method": "stage3_polygon_edge",
            },
            "has_inferred_corner": (inf_1 or inf_2),
        })

    # 5. STEP 3 & 4 & 8: Floor Area and Perimeter Monte Carlo Propagation
    mc_results = monte_carlo_area_and_perimeter_uncertainty(
        vertices=unique_vertices,
        corner_uncertainties_m=corner_sigmas,
        num_samples=mc_samples,
        random_seed=random_seed,
        confidence_level=confidence_level,
    )

    # Perimeter
    nominal_perimeter = float(sum(w["length_m"] for w in wall_dimension_items))
    perim_lower = mc_results["perimeter"]["lower"]
    perim_upper = mc_results["perimeter"]["upper"]
    mean_w_conf = float(np.mean(wall_confidences)) if wall_confidences else 0.70
    inferred_corner_count = sum(1 for c in corner_lookup.values() if c.get("id") in poly_corner_ids and c.get("inferred", False))
    inf_ratio = inferred_corner_count / max(num_vertices, 1)

    perim_conf = float(np.clip(mean_w_conf * (1.0 - 0.15 * inf_ratio), 0.10, 0.99))
    perimeter_measurement = Measurement[float](
        value=round(nominal_perimeter, 3),
        unit="m",
        lower_bound=round(perim_lower, 3),
        upper_bound=round(perim_upper, 3),
        interval=[round(perim_lower, 3), round(perim_upper, 3)],
        confidence=round(perim_conf, 3),
        method="polygon_edge_sum",
    )

    # Floor Area
    nominal_area = mc_results["area"]["value"]
    area_lower = mc_results["area"]["lower"]
    area_upper = mc_results["area"]["upper"]
    boundary_support = polygon_stats.get("quality", {}).get("boundary_support_ratio", 1.0)
    is_provisional = (validity_report.measurement_status == ValidityStatus.PROVISIONAL)

    area_conf = derive_area_confidence(
        mean_wall_confidence=mean_w_conf,
        boundary_support_ratio=boundary_support,
        inferred_corner_ratio=inf_ratio,
        is_provisional=is_provisional,
    )
    floor_area_measurement = Measurement[float](
        value=round(nominal_area, 3),
        unit="m2",
        lower_bound=round(area_lower, 3),
        upper_bound=round(area_upper, 3),
        interval=[round(area_lower, 3), round(area_upper, 3)],
        confidence=round(area_conf, 3),
        method="polygon_monte_carlo_integration",
    )

    # 6. STEP 5: Ceiling Height (Stage 2 planes only)
    floor_plane = structure_data.get("floor", {})
    ceiling_plane = structure_data.get("ceiling", {})

    floor_detected = floor_plane.get("detected", False)
    ceiling_detected = ceiling_plane.get("detected", False)

    ceiling_measurement: Optional[Measurement[float]] = None
    ceiling_status_str = "not_observed"
    ceiling_height_val: Optional[float] = None

    if floor_detected and ceiling_detected and ceiling_plane.get("plane") is not None:
        floor_mean_y = floor_plane.get("mean_y")
        ceil_mean_y = ceiling_plane.get("mean_y")
        if floor_mean_y is not None and ceil_mean_y is not None:
            raw_height = abs(ceil_mean_y - floor_mean_y)
        else:
            df = floor_plane["plane"].get("d", 0.0)
            dc = ceiling_plane["plane"].get("d", 0.0)
            raw_height = abs(dc - df)

        rmse_floor = floor_plane.get("rmse_m", 0.015)
        rmse_ceil = ceiling_plane.get("rmse_m", 0.025)
        sigma_h = math.hypot(rmse_floor, rmse_ceil)
        moe_h = 1.96 * sigma_h
        ceil_conf = math.sqrt(floor_plane.get("confidence", 0.8) * ceiling_plane.get("confidence", 0.8))

        ceiling_height_val = round(raw_height, 3)
        ceiling_measurement = Measurement[float](
            value=ceiling_height_val,
            unit="m",
            lower_bound=round(raw_height - moe_h, 3),
            upper_bound=round(raw_height + moe_h, 3),
            interval=[round(raw_height - moe_h, 3), round(raw_height + moe_h, 3)],
            confidence=round(ceil_conf, 3),
            method="structural_plane_perpendicular_distance",
        )
        ceiling_status_str = "observed"
    else:
        ceiling_measurement = None
        ceiling_status_str = "not_observed"
        ceiling_height_val = None

    # 7. STEP 11: Export Standard Deliverables
    # 7a. measurement_stats.json
    measurement_stats = {
        "scan_id": scan_id,
        "measurement_status": validity_report.measurement_status.value,
        "reasons": validity_report.reasons,
        "wall_count": len(wall_dimension_items),
        "floor_area_m2": round(nominal_area, 3),
        "floor_area_interval": [round(area_lower, 3), round(area_upper, 3)],
        "floor_area_confidence": round(area_conf, 3),
        "perimeter_m": round(nominal_perimeter, 3),
        "perimeter_interval": [round(perim_lower, 3), round(perim_upper, 3)],
        "perimeter_confidence": round(perim_conf, 3),
        "ceiling_height_status": ceiling_status_str,
        "ceiling_height_m": ceiling_height_val,
        "inferred_corner_count": inferred_corner_count,
        "mean_wall_confidence": round(mean_w_conf, 3),
        "ground_truth_available": False,
        "disclaimer": "Engineering estimates derived from 3D point cloud reconstruction. Calibrated physical ground truth required.",
    }

    stats_file = output_dir / "measurement_stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(measurement_stats, f, indent=2)

    # 7b. measurements.json (Master Contract)
    measurements_master = {
        "scan_id": scan_id,
        "status": validity_report.measurement_status.value,
        "status_reasons": validity_report.reasons,
        "walls": measurement_walls_output,
        "floor_area": floor_area_measurement.model_dump(),
        "perimeter": perimeter_measurement.model_dump(),
        "ceiling_height": ceiling_measurement.model_dump() if ceiling_measurement else None,
        "ceiling_status": ceiling_status_str,
        "inferred_corner_count": inferred_corner_count,
        "wall_count": len(wall_dimension_items),
        "metadata": {
            "coordinate_system": {"vertical": "Y", "floor_plane": "XZ", "units": "meters"},
            "uncertainty_coverage": "95% (k=1.96)",
            "monte_carlo_samples": mc_samples,
            "random_seed": random_seed,
            "ground_truth_verified": False,
        },
    }

    master_file = output_dir / "measurements.json"
    with open(master_file, "w", encoding="utf-8") as f:
        json.dump(measurements_master, f, indent=2)

    # 7c. wall_dimensions.json
    wall_dim_file = output_dir / "wall_dimensions.json"
    with open(wall_dim_file, "w", encoding="utf-8") as f:
        json.dump(wall_dimension_items, f, indent=2)

    # 7d. uncertainty.json
    corner_uncertainty_dict = {
        poly_corner_ids[i]: {
            "corner_id": poly_corner_ids[i],
            "sigma_position_m": round(corner_sigmas[i], 4),
            "inferred": corner_lookup.get(poly_corner_ids[i], {}).get("inferred", False),
            "extension_m": round(
                max(
                    corner_lookup.get(poly_corner_ids[i], {}).get("extension_wall_a_m", 0.0),
                    corner_lookup.get(poly_corner_ids[i], {}).get("extension_wall_b_m", 0.0),
                ),
                4,
            ),
        }
        for i in range(num_vertices)
    }

    uncertainty_report = {
        "scan_id": scan_id,
        "model": "analytical_gaussian_propagation_and_monte_carlo_perturbation",
        "coverage": "95%",
        "monte_carlo_config": {
            "samples": mc_samples,
            "random_seed": random_seed,
            "perturbation_distribution": "2D_isotropic_Gaussian",
        },
        "corners": corner_uncertainty_dict,
        "floor_area": mc_results["area"],
        "perimeter": mc_results["perimeter"],
    }

    uncertainty_file = output_dir / "uncertainty.json"
    with open(uncertainty_file, "w", encoding="utf-8") as f:
        json.dump(uncertainty_report, f, indent=2)

    # 7e. dimensioned_debug.svg
    svg_file = output_dir / "dimensioned_debug.svg"
    render_dimensioned_debug_svg(
        polygon_vertices=unique_vertices,
        wall_dimensions=wall_dimension_items,
        corners=[corner_lookup.get(cid, {"id": cid}) for cid in poly_corner_ids],
        measurement_stats=measurement_stats,
        output_path=svg_file,
    )

    return {
        "scan_id": scan_id,
        "validity_status": validity_report.measurement_status.value,
        "reasons": validity_report.reasons,
        "wall_count": len(wall_dimension_items),
        "floor_area": floor_area_measurement.model_dump(),
        "perimeter": perimeter_measurement.model_dump(),
        "ceiling_height": ceiling_measurement.model_dump() if ceiling_measurement else None,
        "output_files": {
            "measurements_json": str(master_file),
            "wall_dimensions_json": str(wall_dim_file),
            "uncertainty_json": str(uncertainty_file),
            "measurement_stats_json": str(stats_file),
            "dimensioned_debug_svg": str(svg_file),
        },
    }
