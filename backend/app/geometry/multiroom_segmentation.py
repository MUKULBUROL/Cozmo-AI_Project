"""Stage 6 Multi-Room Region Detection & Unified Polygon Extraction.

1. Why this file exists:
    Segments full-property 3D structural geometry and camera trajectory into
    discrete room regions (e.g. Room 01, Room 02, Room 03, Connector 01) using
    structural free-space partitioning while strictly preserving a single, unified
    global coordinate frame (XZ floor plane in meters) and guaranteeing zero impossible
    room overlaps.

2. Pipeline stage:
    Stage 6 — Room Region Detection & Global Polygon Extraction.

3. Inputs:
    List of 3D WallPlanes from structural extraction, camera poses, and optional bounds.

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
    Sparse or noisy wall planes falling back to trajectory-based Manhattan partitioning.

9. What a developer should inspect first:
    Verify that polygon coordinates are in global coordinates and pairwise intersections are zero.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from scipy.cluster.vq import kmeans2
from shapely.geometry import box, Polygon, Point, MultiPoint
from shapely.ops import unary_union

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


def extract_dominant_orientation(
    poses: List[Pose6D],
    wall_planes: Optional[List[Dict[str, Any]]] = None,
) -> float:
    """Computes the primary Manhattan orientation angle theta of the building in radians.

    Parameters:
        poses: Camera trajectory poses.
        wall_planes: Optional structural wall planes from Stage 2.

    Returns:
        Dominant angle theta in radians [0, pi/2).
    """
    angles: List[float] = []
    if wall_planes:
        for w in wall_planes:
            norm = w.get("normal")
            if norm and len(norm) >= 3:
                nx, nz = float(norm[0]), float(norm[2])
                norm_len = math.hypot(nx, nz)
                if norm_len > 1e-4:
                    ang = math.atan2(nz, nx) % (math.pi / 2.0)
                    angles.append(ang)

    if len(angles) >= 2:
        return float(np.median(angles))

    # Fallback to trajectory covariance / PCA
    if poses and len(poses) >= 4:
        pos_xz = np.array([[p.x, p.z] for p in poses], dtype=np.float64)
        cov = np.cov(pos_xz.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        primary_vec = eigvecs[:, int(np.argmax(eigvals))]
        return float(math.atan2(primary_vec[1], primary_vec[0]) % (math.pi / 2.0))

    return 0.0


def _cluster_1d_lines(values: List[float], tolerance_m: float = 0.8) -> List[float]:
    """Clusters 1D divider coordinates within a tolerance threshold."""
    if not values:
        return []
    sorted_vals = sorted(values)
    clusters: List[List[float]] = [[sorted_vals[0]]]
    for v in sorted_vals[1:]:
        if v - clusters[-1][-1] <= tolerance_m:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [float(np.mean(c)) for c in clusters]


def _rotate_polygon(poly: Any, cos_t: float, sin_t: float) -> Polygon:
    """Rotates a Shapely Polygon (or largest component of MultiPolygon) using direct matrix coordinates."""
    if hasattr(poly, "geoms"):
        poly = max(poly.geoms, key=lambda g: g.area)
    coords = list(poly.exterior.coords)
    rot_coords = [(x * cos_t - y * sin_t, x * sin_t + y * cos_t) for x, y in coords]
    return Polygon(rot_coords)


def cluster_trajectory_into_room_regions(
    poses: List[Pose6D],
    target_clusters: int = 4,
    wall_planes: Optional[List[Dict[str, Any]]] = None,
) -> List[SegmentedRoomCandidate]:
    """Partitions camera trajectory and space into discrete, non-overlapping room regions.

    Purpose:
        Constructs a clean structural free-space partition of the building aligned with
        the dominant architectural Manhattan frame, strictly guaranteeing zero impossible
        room overlaps and modeling hallways as realistic corridors rather than diagonal wedges.

    Parameters:
        poses: Chronological list of Pose6D poses.
        target_clusters: Desired room count (typically 3 to 4 for multi-room properties).
        wall_planes: Optional structural wall planes from Stage 2 extraction.

    Returns:
        List of SegmentedRoomCandidate objects with global centroids and polygon cells.
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

    # 1. Compute dominant Manhattan orientation theta
    theta = extract_dominant_orientation(poses, wall_planes)
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    # 2. Transform poses to Manhattan frame (u, v)
    u_vals = positions_xz[:, 0] * cos_t + positions_xz[:, 1] * sin_t
    v_vals = -positions_xz[:, 0] * sin_t + positions_xz[:, 1] * cos_t
    uv_poses = np.column_stack((u_vals, v_vals))

    u_min, u_max = float(u_vals.min()), float(u_vals.max())
    v_min, v_max = float(v_vals.min()), float(v_vals.max())

    # 3. Project structural walls to discover Manhattan dividing lines
    u_divs: List[float] = []
    v_divs: List[float] = []

    if wall_planes:
        for w in wall_planes:
            cent = w.get("centroid")
            norm = w.get("normal")
            if not cent or not norm:
                continue
            cx, cz = float(cent[0]), float(cent[2])
            nx, nz = float(norm[0]), float(norm[2])

            cu = cx * cos_t + cz * sin_t
            cv = -cx * sin_t + cz * cos_t
            nu = nx * cos_t + nz * sin_t
            nv = -nx * sin_t + nz * cos_t

            if abs(nu) > abs(nv):
                u_divs.append(cu)
            else:
                v_divs.append(cv)

    u_clustered = _cluster_1d_lines(u_divs, tolerance_m=0.8)
    v_clustered = _cluster_1d_lines(v_divs, tolerance_m=0.8)

    # Ensure bounding dividers enclose the trajectory
    margin = 0.4
    u_bounds = sorted(list(set(
        [u_min - margin] +
        [u for u in u_clustered if u_min - margin <= u <= u_max + margin] +
        [u_max + margin]
    )))
    v_bounds = sorted(list(set(
        [v_min - margin] +
        [v for v in v_clustered if v_min - margin <= v <= v_max + margin] +
        [v_max + margin]
    )))

    # Fallback to k-means regular grid if wall dividers are too few
    if len(u_bounds) < 3:
        u_bounds = sorted([u_min - margin, (u_min + u_max) / 2.0, u_max + margin])
    if len(v_bounds) < 3:
        v_bounds = sorted([v_min - margin, (v_min + v_max) / 2.0, v_max + margin])

    # 4. Form rectangular structural cells in (u, v) and evaluate trajectory occupancy
    active_cells: List[Dict[str, Any]] = []
    for i in range(len(u_bounds) - 1):
        for j in range(len(v_bounds) - 1):
            u0, u1 = u_bounds[i], u_bounds[i + 1]
            v0, v1 = v_bounds[j], v_bounds[j + 1]
            cell_poly = box(u0, v0, u1, v1)

            # Inliers
            in_mask = (u_vals >= u0) & (u_vals < u1) & (v_vals >= v0) & (v_vals < v1)
            frame_indices = [frame_ids[k] for k in range(len(poses)) if in_mask[k]]

            if len(frame_indices) >= max(10, len(poses) // 100):
                active_cells.append({
                    "u_range": (u0, u1),
                    "v_range": (v0, v1),
                    "poly": cell_poly,
                    "frames": frame_indices,
                    "centroid_uv": (float((u0 + u1) / 2.0), float((v0 + v1) / 2.0)),
                    "area": float(cell_poly.area),
                })

    # 5. Group active cells into semantic rooms and connecting hallway
    # In multi-room apartments, the central transitional band (mid-V) acts as the hallway connector
    v_mid_range = (v_min + (v_max - v_min) * 0.35, v_min + (v_max - v_min) * 0.65)
    candidates: List[SegmentedRoomCandidate] = []

    # Identify connector cells: cells that lie within the central transition band connecting wings
    conn_cells = []
    room_cell_groups: Dict[str, List[Dict[str, Any]]] = {
        "north_west": [],
        "north_east": [],
        "south_east": [],
        "south_west": [],
    }

    u_mid = (u_min + u_max) / 2.0

    for c in active_cells:
        cu, cv = c["centroid_uv"]
        # If cell spans across central hallway band with high aspect ratio or central V
        is_in_hallway_band = (v_mid_range[0] <= cv <= v_mid_range[1])
        if is_in_hallway_band and len(active_cells) > 3:
            conn_cells.append(c)
        else:
            if cv >= v_mid_range[1]:
                if cu < u_mid:
                    room_cell_groups["north_west"].append(c)
                else:
                    room_cell_groups["north_east"].append(c)
            else:
                if cu >= u_mid:
                    room_cell_groups["south_east"].append(c)
                else:
                    room_cell_groups["south_west"].append(c)

    # Construct Connector Polygon
    conn_poly_uv = None
    conn_frames: List[int] = []
    if conn_cells:
        conn_poly_uv = unary_union([c["poly"] for c in conn_cells])
        for c in conn_cells:
            conn_frames.extend(c["frames"])

    # If connector cells are empty or disconnected, fallback to most central active cell
    if conn_poly_uv is None or conn_poly_uv.is_empty:
        if active_cells:
            # Pick cell closest to overall trajectory center
            c_center = (float(np.mean(u_vals)), float(np.mean(v_vals)))
            best_idx = int(np.argmin([math.hypot(c["centroid_uv"][0] - c_center[0], c["centroid_uv"][1] - c_center[1]) for c in active_cells]))
            conn_cell = active_cells.pop(best_idx)
            conn_poly_uv = conn_cell["poly"]
            conn_frames = conn_cell["frames"]

    # Assemble non-overlapping room polygons from the cell groups
    room_counter = 1
    for grp_key in ["north_west", "north_east", "south_east", "south_west"]:
        group = room_cell_groups[grp_key]
        if not group:
            continue

        grp_poly = unary_union([c["poly"] for c in group])
        if conn_poly_uv is not None and not conn_poly_uv.is_empty:
            grp_poly = grp_poly.difference(conn_poly_uv)

        if grp_poly.is_empty or grp_poly.area < 1.0:
            continue

        grp_frames: List[int] = []
        for c in group:
            grp_frames.extend(c["frames"])

        # Rotate back to global frame (x, z)
        global_poly = _rotate_polygon(grp_poly, cos_t, -sin_t)
        gc_x, gc_z = float(global_poly.centroid.x), float(global_poly.centroid.y)

        candidates.append(
            SegmentedRoomCandidate(
                room_id=f"room_{room_counter:02d}",
                is_connector=False,
                trajectory_indices=grp_frames,
                centroid_xz=(gc_x, gc_z),
                cell_polygon=global_poly,
            )
        )
        room_counter += 1

    # Add connector candidate
    if conn_poly_uv is not None and not conn_poly_uv.is_empty:
        global_conn_poly = _rotate_polygon(conn_poly_uv, cos_t, -sin_t)
        gcc_x, gcc_z = float(global_conn_poly.centroid.x), float(global_conn_poly.centroid.y)
        candidates.append(
            SegmentedRoomCandidate(
                room_id="connector_01",
                is_connector=True,
                trajectory_indices=conn_frames,
                centroid_xz=(gcc_x, gcc_z),
                cell_polygon=global_conn_poly,
            )
        )

    # Sort rooms sequentially, keeping connector at the end
    candidates.sort(key=lambda x: (x.is_connector, x.room_id))
    return candidates


def assign_walls_to_rooms(
    wall_planes: List[Dict[str, Any]],
    room_candidates: List[SegmentedRoomCandidate],
    max_wall_distance_m: float = 4.0,
) -> None:
    """Associates structural wall planes with candidate room regions based on proximity."""
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
    """Constructs a valid 2D room polygon strictly maintaining global coordinates."""
    if cell_polygon is not None and cell_polygon.is_valid and cell_polygon.area > 1.0:
        # If multi-polygon, select largest component
        if hasattr(cell_polygon, "geoms"):
            cell_polygon = max(cell_polygon.geoms, key=lambda g: g.area)

        coords = list(cell_polygon.exterior.coords)
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
            length_m = math.hypot(p_end.x - p_start.x, p_end.y - p_start.y)
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
