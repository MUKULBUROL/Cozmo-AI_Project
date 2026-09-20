"""Stage 8 evidence-gated multi-room photo alignment and Stage 6.1 property reuse.

1. Why this file exists:
   Places independently reconstructed room folders into one property frame only when connector or
   shared-cloud evidence supports relative rigid transforms.
2. Pipeline stage:
   Stage 8, Steps 23-30 (room-local reconstruction, stitching, topology, and property output).
3. Inputs:
   Property child folders with 2-8 stills each, room-local polygons, and metric point clouds.
4. Outputs:
   Per-room outputs, local-to-global transforms, ``room_alignment.svg``, ``property_debug.svg``,
   and shared Stage 6.1 ``property.json`` or ``PROPERTY_STITCH_NOT_EVALUABLE``.
5. Coordinate system:
   Local and global geometry are right-handed Y-up meters; floor polygons use XZ meters.
6. Units:
   Translations/RMSE are meters, yaw is degrees, scale is unitless and constrained to one.
7. Dependencies:
   Open3D registration, NumPy, Shapely, and existing Stage 6.1 topology/serialization.
8. Assumptions:
   Connector folders overlap visually/geometrically with adjacent room captures.
9. Failure modes:
   Missing valid polygons/clouds, weak registration, disconnected evidence, scale inconsistency,
   or impossible transformed room overlap.
10. First debugging points:
   Inspect each room stats, pairwise registration evidence, alignments, and overlap violations.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import open3d as o3d
from shapely.geometry import Polygon
from shapely.ops import unary_union

from backend.app.geometry.property_topology import (
    assemble_property_plan_output,
    build_room_adjacency_graph,
    export_property_json,
    validate_room_topology,
)
from backend.app.geometry.property_viz import render_property_debug_svg
from backend.app.models.capture import CaptureTier
from backend.app.models.floorplan import Point2D, Room2D, Wall2D
from backend.app.pipelines.photo.ingestion import discover_photo_files
from backend.app.pipelines.photo.models import RoomAlignment
from backend.app.pipelines.photo.pipeline import run_photo_room_pipeline


def room_from_polygon_artifact(room_id: str, polygon_path: Path) -> Room2D | None:
    """Load one valid Stage 3 room polygon into the shared Stage 6.1 model.

    Parameters:
        room_id: Stable folder-derived room identifier, not an ordering cue.
        polygon_path: Shared Stage 3 ``room_polygon.json`` path.
    Returns:
        ``Room2D`` in local XZ meters or ``None`` for missing/invalid/open geometry.
    Coordinates/units:
        JSON vertex pairs are local XZ meters and become ``Point2D(x, y=z)``.
    Assumptions:
        Stage 3 repeats the first vertex at closure; this loader removes that duplicate.
    Failure/debugging:
        Malformed JSON propagates; invalid polygons return ``None``. Inspect Stage 3 artifacts.
    """
    if not polygon_path.exists():
        return None
    with open(polygon_path, "r", encoding="utf-8") as source:
        data = json.load(source)
    polygon = data.get("polygon", {})
    if not polygon.get("valid") or not polygon.get("closed"):
        return None
    vertices = polygon.get("vertices", [])
    if len(vertices) > 1 and np.allclose(vertices[0], vertices[-1]):
        vertices = vertices[:-1]
    if len(vertices) < 3:
        return None
    points = [Point2D(x=float(vertex[0]), y=float(vertex[1])) for vertex in vertices]
    walls = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        walls.append(Wall2D(wall_id=f"{room_id}_wall_{index + 1:02d}", start=start, end=end, length_meters=math.hypot(end.x - start.x, end.y - start.y)))
    shape = Polygon([(point.x, point.y) for point in points])
    return Room2D(room_id=room_id, name="Hallway Connector" if "connector" in room_id.casefold() else room_id.replace("_", " ").title(), polygon=points, area_sqm=float(shape.area), perimeter_meters=float(shape.length), walls=walls)


def transform_room_to_global(room: Room2D, transform: np.ndarray) -> Room2D:
    """Apply one rigid 4x4 local-to-global transform to a shared room model.

    Parameters:
        room: Local XZ meter room polygon and walls.
        transform: Homogeneous 4x4 global-from-local transform with unit scale.
    Returns:
        New ``Room2D`` preserving IDs and recomputing global metric area/perimeter.
    Coordinates/units:
        Input/output are Y-up meters; local floor points embed as ``[x, 0, z, 1]``.
    Assumptions:
        Transform is rigid; callers validate singular values before use.
    Failure/debugging:
        Raises ``ValueError`` for malformed/non-rigid transforms. Inspect registration evidence.
    """
    transform = np.asarray(transform, dtype=np.float64)
    if transform.shape != (4, 4) or not np.all(np.isfinite(transform)):
        raise ValueError("Room transform must be a finite 4x4 matrix")
    singular_values = np.linalg.svd(transform[:3, :3], compute_uv=False)
    if not np.allclose(singular_values, 1.0, atol=0.03) or np.linalg.det(transform[:3, :3]) < 0.0:
        raise ValueError(f"Room transform is not rigid unit-scale: singular values {singular_values}")
    transformed = []
    for point in room.polygon:
        global_point = transform @ np.array([point.x, 0.0, point.y, 1.0])
        transformed.append(Point2D(x=float(global_point[0]), y=float(global_point[2])))
    shape = Polygon([(point.x, point.y) for point in transformed])
    walls = []
    for index, start in enumerate(transformed):
        end = transformed[(index + 1) % len(transformed)]
        walls.append(Wall2D(wall_id=room.walls[index].wall_id if index < len(room.walls) else f"{room.room_id}_wall_{index + 1:02d}", start=start, end=end, length_meters=math.hypot(end.x - start.x, end.y - start.y)))
    return Room2D(room_id=room.room_id, name=room.name, polygon=transformed, area_sqm=float(shape.area), perimeter_meters=float(shape.length), walls=walls, openings=room.openings)


def solve_alignment_graph(
    room_ids: List[str],
    evidence_edges: List[Dict[str, Any]],
) -> Tuple[Dict[str, np.ndarray], List[str]]:
    """Compose pairwise connector registrations into traceable global room transforms.

    Parameters:
        room_ids: Required room/connector IDs.
        evidence_edges: Records with ``target``, ``source``, and target-from-source ``transform``.
    Returns:
        Mapping of global-from-local transforms and disconnected room IDs.
    Coordinates/units:
        Transform translations are meters in Y-up world coordinates.
    Assumptions:
        Every accepted edge is independently quality-gated and unit-scale rigid.
    Failure/debugging:
        Empty/disconnected graphs return missing IDs, not guessed transforms. Inspect edge fitness.
    """
    adjacency: Dict[str, List[Tuple[str, np.ndarray]]] = defaultdict(list)
    for edge in evidence_edges:
        target, source = str(edge["target"]), str(edge["source"])
        target_from_source = np.asarray(edge["transform"], dtype=np.float64)
        adjacency[target].append((source, target_from_source))
        adjacency[source].append((target, np.linalg.inv(target_from_source)))
    if not room_ids:
        return {}, []
    anchor = sorted(room_ids, key=lambda room_id: (-len(adjacency[room_id]), room_id))[0]
    transforms = {anchor: np.eye(4)}
    queue = deque([anchor])
    while queue:
        current = queue.popleft()
        for neighbor, current_from_neighbor in adjacency[current]:
            if neighbor in transforms:
                continue
            transforms[neighbor] = transforms[current] @ current_from_neighbor
            queue.append(neighbor)
    missing = sorted(set(room_ids) - set(transforms))
    return transforms, missing


def register_room_clouds(target_path: Path, source_path: Path, voxel_m: float = 0.10) -> Dict[str, Any]:
    """Estimate target-from-source rigid alignment from overlapping metric room clouds.

    Parameters:
        target_path/source_path: Y-up metric PLY files from independent room reconstructions.
        voxel_m: Registration feature/downsample resolution in meters.
    Returns:
        Transform, fitness, RMSE, accepted flag, and observed shared-cloud evidence label.
    Coordinates/units:
        Transform/RMSE are target-frame meters; no similarity scale is estimated.
    Assumptions:
        Connector photographs create enough shared structural surface for FPFH/RANSAC and ICP.
    Failure/debugging:
        Sparse/non-overlapping clouds return ``accepted=False``. Inspect cloud density and overlap.
    """
    target = o3d.io.read_point_cloud(str(target_path))
    source = o3d.io.read_point_cloud(str(source_path))
    if len(target.points) < 100 or len(source.points) < 100:
        return {"accepted": False, "reason": "insufficient_cloud_points", "fitness": 0.0, "rmse_m": None}
    target_down = target.voxel_down_sample(voxel_m)
    source_down = source.voxel_down_sample(voxel_m)
    for cloud in (target_down, source_down):
        cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_m * 2.0, max_nn=30))
    target_feature = o3d.pipelines.registration.compute_fpfh_feature(target_down, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_m * 5.0, max_nn=100))
    source_feature = o3d.pipelines.registration.compute_fpfh_feature(source_down, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_m * 5.0, max_nn=100))
    coarse = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        source_down, target_down, source_feature, target_feature, True, voxel_m * 1.5,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 3,
        [o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9), o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(voxel_m * 1.5)],
        o3d.pipelines.registration.RANSACConvergenceCriteria(50000, 0.999),
    )
    refined = o3d.pipelines.registration.registration_icp(source, target, voxel_m, coarse.transformation, o3d.pipelines.registration.TransformationEstimationPointToPlane())
    accepted = bool(refined.fitness >= 0.18 and refined.inlier_rmse <= 0.20)
    return {"accepted": accepted, "reason": None if accepted else "weak_shared_geometry", "fitness": float(refined.fitness), "rmse_m": float(refined.inlier_rmse), "transform": refined.transformation.tolist(), "evidence": "observed_shared_metric_cloud"}


def assemble_stitched_property(
    capture_id: str,
    local_rooms: Dict[str, Room2D],
    evidence_edges: List[Dict[str, Any]],
    output_dir: Path,
) -> Dict[str, Any]:
    """Transform rooms, validate Stage 6.1 topology, and serialize one property plan.

    Parameters:
        capture_id: Property identifier.
        local_rooms: Valid room-local Stage 3 polygons.
        evidence_edges: Accepted pairwise rigid registrations.
        output_dir: Property artifact directory.
    Returns:
        Status, alignments, adjacency, overlap, and footprint summary.
    Coordinates/units:
        All transformed room polygons are global XZ meters.
    Assumptions:
        Evidence edges encode geometry, never folder-order adjacency.
    Failure/debugging:
        Disconnected graphs or overlap violations emit ``PROPERTY_STITCH_NOT_EVALUABLE`` without
        a guessed shared serializer output. Inspect missing rooms and topology report.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    transforms, missing = solve_alignment_graph(list(local_rooms), evidence_edges)
    if missing or len(transforms) != len(local_rooms):
        report = {"capture_id": capture_id, "tier": "photo", "status": "PROPERTY_STITCH_NOT_EVALUABLE", "rooms": [], "connections": [], "failure_reasons": ["disconnected_alignment_evidence"], "unaligned_rooms": missing}
        (output_dir / "property.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        render_property_debug_svg([], [], scan_id=capture_id, drift_status="NOT EVALUABLE", output_path=output_dir / "property_debug.svg")
        (output_dir / "room_alignment.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="300"><text x="20" y="40">PROPERTY_STITCH_NOT_EVALUABLE: disconnected alignment evidence</text></svg>', encoding="utf-8")
        return report
    global_rooms = [transform_room_to_global(local_rooms[room_id], transforms[room_id]) for room_id in sorted(local_rooms)]
    topology = validate_room_topology(global_rooms, max_allowable_overlap_ratio=0.02, max_allowable_overlap_area_sqm=0.05)
    alignments = []
    for room_id in sorted(transforms):
        transform = transforms[room_id]
        yaw = math.degrees(math.atan2(transform[0, 2], transform[0, 0]))
        alignments.append(RoomAlignment(room_id=room_id, translation_x_m=float(transform[0, 3]), translation_z_m=float(transform[2, 3]), yaw_degrees=yaw, evidence=["observed_shared_metric_cloud"] if evidence_edges else [], confidence=min([edge.get("fitness", 0.0) for edge in evidence_edges], default=1.0)).model_dump())
    if not topology.is_valid:
        report = {"capture_id": capture_id, "tier": "photo", "status": "PROPERTY_STITCH_NOT_EVALUABLE", "rooms": [], "connections": [], "failure_reasons": ["impossible_room_overlap"], "overlap_violations": topology.overlap_violations, "alignments": alignments}
        (output_dir / "property.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        render_property_debug_svg(global_rooms, [], scan_id=capture_id, drift_status="ALIGNMENT REJECTED", output_path=output_dir / "property_debug.svg")
        (output_dir / "room_alignment.svg").write_text(render_property_debug_svg(global_rooms, [], scan_id=f"{capture_id} room alignment", drift_status="REJECTED"), encoding="utf-8")
        return report
    connections = build_room_adjacency_graph(global_rooms)
    property_output = assemble_property_plan_output(capture_id, global_rooms, connections, "not_evaluable", 0.0, capture_tier=CaptureTier.PHOTO, reconstruction_method="photo_room_sfm_connector_cloud_alignment")
    export_property_json(property_output, output_dir / "property.json")
    render_property_debug_svg(global_rooms, connections, scan_id=capture_id, drift_status="PHOTO CONNECTOR ALIGNMENT", output_path=output_dir / "property_debug.svg")
    (output_dir / "room_alignment.svg").write_text(render_property_debug_svg(global_rooms, connections, scan_id=f"{capture_id} room alignment", drift_status="OBSERVED + INFERRED ADJACENCY"), encoding="utf-8")
    footprint = float(unary_union([Polygon([(point.x, point.y) for point in room.polygon]) for room in global_rooms]).area) if global_rooms else 0.0
    return {"capture_id": capture_id, "tier": "photo", "status": "PROVISIONAL", "rooms_reconstructed": len(global_rooms), "alignments": alignments, "connectors": len([room for room in global_rooms if "connector" in room.room_id.casefold()]), "adjacency_edges": len(connections), "overlap_violations": [], "footprint_sqm": footprint, "topology_valid": True}


def run_photo_property_pipeline(input_dir: Path, output_dir: Path, capture_id: str, synthetic_development_set: bool = False) -> Dict[str, Any]:
    """Reconstruct every child photo folder and attempt evidence-based whole-property stitching.

    Parameters:
        input_dir: Property folder containing arbitrary room/connector child folders.
        output_dir: Stage 8 property output root.
        capture_id: Stable property capture identifier.
        synthetic_development_set: Honest label for video-derived development stills.
    Returns:
        Property reconstruction/stitch summary with separate timing and room statuses.
    Coordinates/units:
        Each room starts local Y-up meters and accepted output is global Y-up meters.
    Assumptions:
        Child folder names identify rooms but do not imply order or adjacency.
    Failure/debugging:
        Fewer than two valid room folders, failed local polygons, or absent connector overlap returns
        ``PROPERTY_STITCH_NOT_EVALUABLE``. Inspect per-room outputs and pairwise evidence JSON.
    """
    started = time.time()
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    child_dirs = sorted([path for path in input_dir.iterdir() if path.is_dir() and len(discover_photo_files(path)) >= 2], key=lambda path: path.name.casefold())
    if len(child_dirs) < 2:
        raise ValueError(f"Property photo input requires at least two room/connector folders: {input_dir}")
    room_summaries: Dict[str, Any] = {}
    local_rooms: Dict[str, Room2D] = {}
    cloud_paths: Dict[str, Path] = {}
    for child in child_dirs:
        room_id = child.name
        room_output = output_dir / "rooms" / room_id
        summary = run_photo_room_pipeline(child, room_output, f"{capture_id}_{room_id}", room_id, synthetic_development_set)
        room_summaries[room_id] = summary
        room = room_from_polygon_artifact(room_id, room_output / "floorplan_geometry" / "room_polygon.json")
        cloud = room_output / "photo_pointcloud_filtered.ply"
        if room is not None and cloud.exists():
            local_rooms[room_id] = room
            cloud_paths[room_id] = cloud
    evidence = []
    connector_ids = [room_id for room_id in local_rooms if "connector" in room_id.casefold()]
    for connector_id in connector_ids:
        for room_id in local_rooms:
            if room_id == connector_id or "connector" in room_id.casefold():
                continue
            registration = register_room_clouds(cloud_paths[connector_id], cloud_paths[room_id])
            registration.update({"target": connector_id, "source": room_id})
            if registration.get("accepted"):
                evidence.append(registration)
    property_dir = output_dir / "property"
    result = assemble_stitched_property(capture_id, local_rooms, evidence, property_dir) if len(local_rooms) >= 2 else {"capture_id": capture_id, "tier": "photo", "status": "PROPERTY_STITCH_NOT_EVALUABLE", "failure_reasons": ["fewer_than_two_valid_room_reconstructions"]}
    result["room_results"] = room_summaries
    result["pairwise_alignment_evidence"] = evidence
    result["runtime_seconds"] = round(time.time() - started, 3)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "property_reconstruction_stats.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
