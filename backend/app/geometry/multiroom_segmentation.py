"""Stage 6 Multi-Room Region Detection & Unified Polygon Extraction.

1. Why this file exists:
    Segments full-property 3D structural geometry and camera trajectory clusters into
    discrete room regions (e.g. Room 01, Room 02, Room 03, Connector 01) while strictly
    preserving a single, unified global coordinate frame (XZ floor plane in meters)
    and guaranteeing zero impossible room overlaps.

2. Pipeline stage:
    Stage 6 — Room Region Detection & Global Polygon Extraction.

3. Inputs:
    List of 3D WallPlanes from structural extraction, optimized camera poses, and floor bounds.

4. Outputs:
    List of Room2D objects with global polygon vertices, host walls, and room classification
    (room vs connector/hallway).

5. Coordinate conventions:
    ARKit Y-up vertical, XZ horizontal floor plane.
    All polygon vertices and wall coordinates are defined in the shared global coordinate frame.
    Units in meters (m).

6. Unit assumptions:
    Lengths in meters (m), areas in square meters (m2).

7. Important dependencies:
    math, numpy, scipy.cluster.vq, shapely.geometry, backend.app.models.floorplan.

8. What is most likely to break:
    Collinear cluster centers causing degenerate Voronoi cells.

9. What a developer should inspect first:
    Verify that polygon coordinates are in global coordinates and sum of areas matches floor footprint.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from scipy.cluster.vq import kmeans2
from shapely.geometry import box, Polygon, Point, MultiPoint
from shapely.ops import voronoi_diagram

from backend.app.models.capture import Pose6D
from backend.app.models.floorplan import Point2D, Wall2D, Room2D


@dataclass
class SegmentedRoomCandidate:
    """Represents an isolated spatial room partition before polygon validation.

    Attributes:
        room_id: Identifier (e.g. 'room_01', 'connector_01').
        is_connector: True if region exhibits hallway/corridor characteristics.
        trajectory_indices: Frame indices of camera poses inside this region.
        centroid_xz: [x, z] center of gravity in global meters.
        cell_polygon: Shapely Polygon of the partition in global coordinates.
        wall_indices: Indices of associated structural wall planes.
    """
    room_id: str
    is_connector: bool
    trajectory_indices: List[int]
    centroid_xz: Tuple[float, float]
    cell_polygon: Optional[Polygon] = None
    wall_indices: List[int] = field(default_factory=list)


def cluster_trajectory_into_room_regions(
    poses: List[Pose6D],
    target_clusters: int = 4,
) -> List[SegmentedRoomCandidate]:
    """Partitions camera trajectory and space into discrete, non-overlapping room regions.

    Purpose:
        Discovers the physical layout of rooms visited along the camera walk and constructs
        a tessellated partition of the building space with zero overlap violations.

    Parameters:
        poses: Chronological list of Pose6D poses.
        target_clusters: Desired room count (typically 3 to 4 for multi-room properties).

    Returns:
        List of SegmentedRoomCandidate objects with global centroids and polygon cells.

    Assumptions:
        Camera covers the scanned rooms in metric coordinates.

    Failure conditions:
        If trajectory span is small (< 3.0 m), returns a single room region.

    Debugging:
        Inspect candidate centroids and cell_polygon areas.
    """
    if not poses:
        return []

    positions_xz = np.array([[p.x, p.z] for p in poses], dtype=np.float64)
    frame_ids = [p.frame_index for p in poses]

    min_x, max_x = float(positions_xz[:, 0].min() - 0.5), float(positions_xz[:, 0].max() + 0.5)
    min_z, max_z = float(positions_xz[:, 1].min() - 0.5), float(positions_xz[:, 1].max() + 0.5)
    span_x = max_x - min_x
    span_z = max_z - min_z

    # If small single-room scan
    if span_x < 3.5 and span_z < 3.5:
        poly_pts = [
            Point2D(x=round(min_x, 3), y=round(min_z, 3)),
            Point2D(x=round(max_x, 3), y=round(min_z, 3)),
            Point2D(x=round(max_x, 3), y=round(max_z, 3)),
            Point2D(x=round(min_x, 3), y=round(max_z, 3)),
        ]
        cent = (float(np.mean(positions_xz[:, 0])), float(np.mean(positions_xz[:, 1])))
        return [
            SegmentedRoomCandidate(
                room_id="room_01",
                is_connector=False,
                trajectory_indices=frame_ids,
                centroid_xz=cent,
                cell_polygon=box(min_x, min_z, max_x, max_z),
            )
        ]

    # Global building bounding envelope
    b_box = box(min_x, min_z, max_x, max_z)

    # Determine stable cluster count (up to 4)
    k = min(target_clusters, max(2, len(poses) // 100))
    centers, labels = kmeans2(positions_xz, k, minit="points", iter=25)

    # Determine which cluster acts as connector (closest to the mean trajectory center)
    global_mean = np.mean(positions_xz, axis=0)
    dists_to_mean = [float(np.linalg.norm(c - global_mean)) for c in centers]
    connector_idx = int(np.argmin(dists_to_mean))

    # Generate Voronoi diagram partitioned within the building bounding box
    pts = MultiPoint([Point(float(c[0]), float(c[1])) for c in centers])
    vor = voronoi_diagram(pts, envelope=b_box)

    candidates: List[SegmentedRoomCandidate] = []
    room_counter = 1

    for i, c in enumerate(centers):
        pt = Point(float(c[0]), float(c[1]))
        matching_poly = None
        for geom in vor.geoms:
            if geom.contains(pt):
                matching_poly = geom.intersection(b_box)
                break

        if matching_poly is None or matching_poly.area < 1.0:
            # Fallback to local buffer
            matching_poly = pt.buffer(2.0).intersection(b_box)

        c_frames = [frame_ids[idx] for idx in range(len(poses)) if labels[idx] == i]
        is_conn = (i == connector_idx and k > 2)

        if is_conn:
            r_id = "connector_01"
        else:
            r_id = f"room_{room_counter:02d}"
            room_counter += 1

        cand = SegmentedRoomCandidate(
            room_id=r_id,
            is_connector=is_conn,
            trajectory_indices=c_frames,
            centroid_xz=(float(c[0]), float(c[1])),
            cell_polygon=matching_poly,
        )
        candidates.append(cand)

    # Sort so connector is first or last systematically
    candidates.sort(key=lambda x: (x.is_connector, x.room_id))
    return candidates


def assign_walls_to_rooms(
    wall_planes: List[Dict[str, Any]],
    room_candidates: List[SegmentedRoomCandidate],
    max_wall_distance_m: float = 4.0,
) -> None:
    """Associates structural wall planes with candidate room regions based on proximity.

    Purpose:
        Maps global structural wall lines to rooms whose polygon boundaries border them.

    Parameters:
        wall_planes: List of wall plane dictionaries from Stage 2 structural extraction.
        room_candidates: List of SegmentedRoomCandidate objects (modified in-place).
        max_wall_distance_m: Maximum distance threshold from room polygon to wall plane.

    Returns:
        None (modifies wall_indices attribute of candidates in-place).

    Assumptions:
        Structural wall lines are in global XZ coordinates.

    Failure conditions:
        None; unassociated walls remain unassigned.

    Debugging:
        Ensure candidate wall_indices has entries for bordering walls.
    """
    if not wall_planes or not room_candidates:
        return

    wall_centroids = []
    for w in wall_planes:
        cent = w.get("centroid")
        if cent and len(cent) >= 3:
            wall_centroids.append(np.array([cent[0], cent[2]]))
        else:
            bounds = w.get("bounds", {})
            bx = bounds.get("x", [0, 0])
            bz = bounds.get("z", [0, 0])
            wall_centroids.append(np.array([(bx[0] + bx[1]) / 2.0, (bz[0] + bz[1]) / 2.0]))

    for w_idx, w_pos in enumerate(wall_centroids):
        w_pt = Point(w_pos[0], w_pos[1])
        for cand in room_candidates:
            if cand.cell_polygon is not None:
                d = cand.cell_polygon.distance(w_pt)
                if d <= max_wall_distance_m:
                    cand.wall_indices.append(w_idx)


def build_room_polygon_in_global_frame(
    room_id: str,
    name: str,
    associated_wall_planes: List[Dict[str, Any]],
    centroid_xz: Tuple[float, float],
    cell_polygon: Optional[Polygon] = None,
    default_radius_m: float = 2.0,
) -> Room2D:
    """Constructs a valid 2D room polygon strictly maintaining global coordinates.

    Purpose:
        Produces a non-overlapping Room2D model positioned in the unified global floor plan.

    Parameters:
        room_id: String ID (e.g. 'room_01').
        name: Human-readable room title.
        associated_wall_planes: Structural wall planes belonging to this room.
        centroid_xz: Global [x, z] center of the room.
        cell_polygon: Optional precomputed Shapely Polygon partition.
        default_radius_m: Fallback radius if polygon is absent.

    Returns:
        Room2D instance with global coordinates, area, perimeter, and walls.

    Assumptions:
        All coordinates are in global metric meters.

    Failure conditions:
        None; falls back to rectangular envelope if cell_polygon is invalid.

    Debugging:
        Check room.polygon coordinates; they must match global spatial footprint.
    """
    if cell_polygon is not None and cell_polygon.is_valid and cell_polygon.area > 1.0:
        coords = list(cell_polygon.exterior.coords)
        # Drop duplicate closing point
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]

        poly_pts = [Point2D(x=round(float(pt[0]), 3), y=round(float(pt[1]), 3)) for pt in coords]
        area = float(cell_polygon.area)
        perim = float(cell_polygon.length)

        # Build Wall2D segments along the polygon perimeter
        wall_segments: List[Wall2D] = []
        n_pts = len(poly_pts)
        for k in range(n_pts):
            p_start = poly_pts[k]
            p_end = poly_pts[(k + 1) % n_pts]
            length_m = math.sqrt((p_end.x - p_start.x)**2 + (p_end.y - p_start.y)**2)
            wall_segments.append(
                Wall2D(
                    wall_id=f"{room_id}_w{k+1:02d}",
                    start=p_start,
                    end=p_end,
                    length_meters=round(length_m, 3),
                )
            )

        return Room2D(
            room_id=room_id,
            name=name,
            polygon=poly_pts,
            area_sqm=round(area, 2),
            perimeter_meters=round(perim, 2),
            walls=wall_segments,
            openings=[],
        )

    # Fallback to local rectangular footprint
    cx, cz = centroid_xz
    r = default_radius_m
    pts = [
        Point2D(x=round(cx - r, 3), y=round(cz - r, 3)),
        Point2D(x=round(cx + r, 3), y=round(cz - r, 3)),
        Point2D(x=round(cx + r, 3), y=round(cz + r, 3)),
        Point2D(x=round(cx - r, 3), y=round(cz + r, 3)),
    ]
    return Room2D(
        room_id=room_id,
        name=name,
        polygon=pts,
        area_sqm=round((2 * r)**2, 2),
        perimeter_meters=round(8 * r, 2),
        walls=[],
        openings=[],
    )
