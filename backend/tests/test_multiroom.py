"""Stage 6 Multi-Room Reconstruction & Topology Tests.

1. Why this file exists:
    Validates multi-room region partitioning, global coordinate preservation,
    connector/hallway modeling, doorway adjacency graph inference, and room
    overlap validation using synthetic multi-room spatial layouts.

2. Pipeline stage:
    Stage 6 — Multi-Room Geometry & Property Contract Verification.

3. Inputs:
    Synthetic room polygons, structural walls, and door opening fixtures.

4. Outputs:
    Unit test assertions verifying topological consistency and valid property models.

5. Coordinate conventions:
    Shared global horizontal XZ floor plane. Metric units in meters.

6. Unit assumptions:
    Distances in meters (m), area in square meters (m2).

7. Important dependencies:
    unittest, shapely.geometry, backend.app.geometry, backend.app.models.

8. What is most likely to break:
    Coordinate shifts destroying global relative room placement.

9. What a developer should inspect first:
    TestMultiRoomTopology and TestAdjacencyInference.
"""

import unittest
from shapely.geometry import Polygon

from backend.app.models.capture import Pose6D
from backend.app.models.floorplan import Room2D, Point2D, Wall2D, RoomAdjacencyEdge
from backend.app.geometry.multiroom_segmentation import (
    SegmentedRoomCandidate,
    build_room_polygon_in_global_frame,
    cluster_trajectory_into_room_regions,
    extract_dominant_orientation,
)
from backend.app.geometry.property_topology import (
    validate_room_topology,
    build_room_adjacency_graph,
    assemble_property_plan_output,
)


class TestMultiRoomReconstruction(unittest.TestCase):
    """Verifies multi-room geometry, global coordinates, and topological validity."""

    def test_global_coordinate_preservation(self):
        """Verifies that room polygons preserve their absolute global coordinates without shifting to local origin."""
        # Create a synthetic room situated at global offset X in [5.0, 9.0], Z in [2.0, 6.0]
        centroid = (7.0, 4.0)
        wall_planes = [
            {"coefficients": [1.0, 0.0, 0.0, -5.0], "bounds": {"min_x": 5.0, "max_x": 5.0, "min_z": 2.0, "max_z": 6.0}},
            {"coefficients": [1.0, 0.0, 0.0, -9.0], "bounds": {"min_x": 9.0, "max_x": 9.0, "min_z": 2.0, "max_z": 6.0}},
            {"coefficients": [0.0, 0.0, 1.0, -2.0], "bounds": {"min_x": 5.0, "max_x": 9.0, "min_z": 2.0, "max_z": 2.0}},
            {"coefficients": [0.0, 0.0, 1.0, -6.0], "bounds": {"min_x": 5.0, "max_x": 9.0, "min_z": 6.0, "max_z": 6.0}},
        ]

        room = build_room_polygon_in_global_frame(
            room_id="room_02",
            name="Bedroom 2",
            associated_wall_planes=wall_planes,
            centroid_xz=centroid,
        )

        self.assertEqual(room.room_id, "room_02")
        # Ensure vertices are in global coordinates [5..9, 2..6], NOT shifted to origin [0..4, 0..4]
        poly_xs = [p.x for p in room.polygon]
        poly_zs = [p.y for p in room.polygon]

        self.assertGreaterEqual(min(poly_xs), 4.8)
        self.assertLessEqual(max(poly_xs), 9.2)
        self.assertGreaterEqual(min(poly_zs), 1.8)
        self.assertLessEqual(max(poly_zs), 6.2)
        # Expected area = 4m x 4m = 16 m2
        self.assertAlmostEqual(room.area_sqm, 16.0, delta=1.0)

    def test_two_connected_rooms_with_connector(self):
        """Verifies multi-room layout consisting of Room 1, Connector Hallway, and Room 2."""
        # Room 1: X in [0, 4], Z in [0, 4]
        r1 = Room2D(
            room_id="room_01",
            name="Living Room",
            polygon=[Point2D(x=0, y=0), Point2D(x=4, y=0), Point2D(x=4, y=4), Point2D(x=0, y=4)],
            area_sqm=16.0,
            perimeter_meters=16.0,
        )

        # Connector (Hallway): X in [4.0, 6.0], Z in [1.5, 2.5] (elongated corridor connecting rooms)
        conn = Room2D(
            room_id="connector_01",
            name="Hallway Connector",
            polygon=[Point2D(x=4, y=1.5), Point2D(x=6, y=1.5), Point2D(x=6, y=2.5), Point2D(x=4, y=2.5)],
            area_sqm=2.0,
            perimeter_meters=6.0,
        )

        # Room 2: X in [6.0, 10.0], Z in [0, 4]
        r2 = Room2D(
            room_id="room_02",
            name="Bedroom",
            polygon=[Point2D(x=6, y=0), Point2D(x=10, y=0), Point2D(x=10, y=4), Point2D(x=6, y=4)],
            area_sqm=16.0,
            perimeter_meters=16.0,
        )

        rooms = [r1, conn, r2]

        # Validate topology: no overlap violations
        report = validate_room_topology(rooms)
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.overlap_violations), 0)

        # Door openings at corridor junctions:
        # Door 1 between Room 1 and Hallway at (4.0, 2.0)
        # Door 2 between Hallway and Room 2 at (6.0, 2.0)
        openings = [
            {"opening_id": "door_01", "position_3d": [4.0, 1.0, 2.0]},
            {"opening_id": "door_02", "position_3d": [6.0, 1.0, 2.0]},
        ]

        edges = build_room_adjacency_graph(rooms, detected_openings=openings)

        # Expected connections: (room_01 <-> connector_01) and (connector_01 <-> room_02)
        self.assertEqual(len(edges), 2)
        pairs = [tuple(sorted([e.room_a_id, e.room_b_id])) for e in edges]
        self.assertIn(("connector_01", "room_01"), pairs)
        self.assertIn(("connector_01", "room_02"), pairs)

    def test_overlapping_room_detection(self):
        """Verifies that impossible physical overlaps are caught and flagged by validator."""
        # Room A: [0, 4] x [0, 4] (area 16)
        r_a = Room2D(
            room_id="room_01",
            name="Room A",
            polygon=[Point2D(x=0, y=0), Point2D(x=4, y=0), Point2D(x=4, y=4), Point2D(x=0, y=4)],
            area_sqm=16.0,
            perimeter_meters=16.0,
        )
        # Room B heavily overlapping Room A: [1, 5] x [1, 5] (overlap area 3x3 = 9 m2 > 50%)
        r_b = Room2D(
            room_id="room_02",
            name="Room B",
            polygon=[Point2D(x=1, y=1), Point2D(x=5, y=1), Point2D(x=5, y=5), Point2D(x=1, y=5)],
            area_sqm=16.0,
            perimeter_meters=16.0,
        )

        report = validate_room_topology([r_a, r_b])
        self.assertFalse(report.is_valid)
        self.assertEqual(len(report.overlap_violations), 1)
        self.assertEqual(report.overlap_violations[0]["room_a"], "room_01")
        self.assertEqual(report.overlap_violations[0]["room_b"], "room_02")
        self.assertGreater(report.overlap_violations[0]["overlap_ratio"], 0.5)

    def test_disconnected_property_handling(self):
        """Verifies that an open or disconnected layout produces valid output with honest connectivity."""
        # Two physically separated rooms with no connecting opening or shared wall
        r_a = Room2D(
            room_id="room_01",
            name="Main House",
            polygon=[Point2D(x=0, y=0), Point2D(x=4, y=0), Point2D(x=4, y=4), Point2D(x=0, y=4)],
            area_sqm=16.0,
            perimeter_meters=16.0,
        )
        r_b = Room2D(
            room_id="room_02",
            name="Detached Shed",
            polygon=[Point2D(x=15, y=15), Point2D(x=18, y=15), Point2D(x=18, y=18), Point2D(x=15, y=18)],
            area_sqm=9.0,
            perimeter_meters=12.0,
        )

        edges = build_room_adjacency_graph([r_a, r_b], detected_openings=[])
        # Disconnected: 0 adjacency edges, but still valid schema
        self.assertEqual(len(edges), 0)

        output = assemble_property_plan_output(
            scan_id="test_disconnected",
            rooms=[r_a, r_b],
            connections=edges,
            drift_status="IMPROVED",
            residual_m=0.015,
        )

        self.assertEqual(len(output.rooms), 2)
        self.assertEqual(len(output.connections), 0)
        self.assertAlmostEqual(output.total_floor_area.value, 25.0)

    def test_manhattan_orientation_extraction(self):
        """Verifies dominant orientation theta is correctly extracted from orthogonal wall planes."""
        # Walls rotated at 30 degrees (0.5236 rad)
        theta_true = 0.5236
        cos_t = 0.8660
        sin_t = 0.5000
        # Wall 1 normal along rotated X: [cos, 0, sin]
        # Wall 2 normal along rotated Z: [-sin, 0, cos]
        wall_planes = [
            {"normal": [cos_t, 0.0, sin_t], "centroid": [0.0, 0.0, 0.0]},
            {"normal": [-sin_t, 0.0, cos_t], "centroid": [2.0, 0.0, 2.0]},
            {"normal": [-cos_t, 0.0, -sin_t], "centroid": [4.0, 0.0, 4.0]},
        ]
        theta_est = extract_dominant_orientation(poses=[], wall_planes=wall_planes)
        self.assertAlmostEqual(theta_est, theta_true, delta=0.05)

    def test_structural_free_space_partitioning_zero_overlap(self):
        """Verifies that multi-room spatial partitioning guarantees strict zero interior overlap."""
        # Create a synthetic trajectory visiting 3 rooms and a hallway
        poses = []
        frame_idx = 0
        # Room 1 cluster (north-west: X in [0..3], Z in [5..8])
        for x in [1.0, 1.5, 2.0, 2.5]:
            for z in [6.0, 6.5, 7.0]:
                poses.append(Pose6D(frame_index=frame_idx, timestamp=float(frame_idx), x=x, y=0.0, z=z, qx=0, qy=0, qz=0, qw=1))
                frame_idx += 1
        # Hallway cluster (central: X in [0..7], Z in [3.5..4.5])
        for x in [1.0, 2.5, 4.0, 5.5]:
            for z in [3.8, 4.0, 4.2]:
                poses.append(Pose6D(frame_index=frame_idx, timestamp=float(frame_idx), x=x, y=0.0, z=z, qx=0, qy=0, qz=0, qw=1))
                frame_idx += 1
        # Room 2 cluster (north-east: X in [5..8], Z in [5..8])
        for x in [5.5, 6.0, 6.5, 7.0]:
            for z in [6.0, 6.5, 7.0]:
                poses.append(Pose6D(frame_index=frame_idx, timestamp=float(frame_idx), x=x, y=0.0, z=z, qx=0, qy=0, qz=0, qw=1))
                frame_idx += 1
        # Room 3 cluster (south-east: X in [5..8], Z in [0..3])
        for x in [5.5, 6.0, 6.5, 7.0]:
            for z in [1.0, 1.5, 2.0]:
                poses.append(Pose6D(frame_index=frame_idx, timestamp=float(frame_idx), x=x, y=0.0, z=z, qx=0, qy=0, qz=0, qw=1))
                frame_idx += 1

        wall_planes = [
            {"normal": [1.0, 0.0, 0.0], "centroid": [0.0, 0.0, 4.0]},
            {"normal": [1.0, 0.0, 0.0], "centroid": [4.5, 0.0, 4.0]},
            {"normal": [1.0, 0.0, 0.0], "centroid": [8.5, 0.0, 4.0]},
            {"normal": [0.0, 0.0, 1.0], "centroid": [4.0, 0.0, 3.2]},
            {"normal": [0.0, 0.0, 1.0], "centroid": [4.0, 0.0, 4.8]},
        ]

        candidates = cluster_trajectory_into_room_regions(poses, wall_planes=wall_planes)
        self.assertGreaterEqual(len(candidates), 3)

        rooms: List[Room2D] = []
        for c in candidates:
            r = build_room_polygon_in_global_frame(
                room_id=c.room_id,
                name="Hallway" if c.is_connector else f"Room {c.room_id}",
                associated_wall_planes=[],
                centroid_xz=c.centroid_xz,
                cell_polygon=c.cell_polygon,
            )
            rooms.append(r)

        # Validate topological consistency: ZERO overlap violations
        report = validate_room_topology(rooms)
        self.assertTrue(report.is_valid)
        self.assertEqual(len(report.overlap_violations), 0)

        # Confirm pairwise polygon intersection area is strictly zero
        for i in range(len(rooms)):
            poly_i = Polygon([(p.x, p.y) for p in rooms[i].polygon])
            for j in range(i + 1, len(rooms)):
                poly_j = Polygon([(p.x, p.y) for p in rooms[j].polygon])
                if poly_i.intersects(poly_j):
                    inter_area = float(poly_i.intersection(poly_j).area)
                    self.assertAlmostEqual(inter_area, 0.0, delta=0.05,
                                           msg=f"Overlap between {rooms[i].room_id} and {rooms[j].room_id}: {inter_area}")


if __name__ == "__main__":
    unittest.main()
