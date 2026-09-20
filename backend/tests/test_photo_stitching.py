"""Stage 8 deterministic tests for room transforms, adjacency, overlaps, and ambiguity.

1. Why this file exists: verifies separate room frames are never joined without transform evidence.
2. Pipeline stage: Stage 8 multi-room photo stitching and Stage 6.1 handoff.
3. Inputs: synthetic metric room polygons and explicit rigid registration edges.
4. Outputs: assertions over global coordinates, adjacency, overlap rejection, and property status.
5. Coordinate system: local/global Y-up worlds with XZ floor polygons.
6. Units: meters, square meters, and rigid homogeneous transforms.
7. Dependencies: NumPy, shared floor-plan models, and Stage 8 stitching.
8. Assumptions: test edges stand in for accepted connector cloud registrations.
9. Failure modes: guessed transforms or topology regressions fail explicit statuses.
10. First debugging points: inspect edge transform convention (target-from-source) and polygons.
"""

from pathlib import Path

import numpy as np

from backend.app.models.floorplan import Point2D, Room2D
from backend.app.pipelines.photo.stitching import assemble_stitched_property, solve_alignment_graph, transform_room_to_global


def _room(room_id: str, width: float = 4.0, depth: float = 3.0) -> Room2D:
    """Create one origin-local rectangular room in metric XZ coordinates.

    Width/depth are meters; the helper returns a shared room model and assumes positive extents.
    Invalid extents should be debugged in the fixture rather than production code.
    """
    return Room2D(room_id=room_id, name=room_id, polygon=[Point2D(x=0, y=0), Point2D(x=width, y=0), Point2D(x=width, y=depth), Point2D(x=0, y=depth)], area_sqm=width * depth, perimeter_meters=2 * (width + depth))


def _translation(x: float, z: float) -> np.ndarray:
    """Return a rigid meter translation homogeneous matrix for synthetic alignment evidence."""
    transform = np.eye(4)
    transform[0, 3], transform[2, 3] = x, z
    return transform


def test_two_room_transform_alignment_and_global_preservation() -> None:
    """Compose target-from-source evidence and preserve the anchor's global coordinates."""
    transforms, missing = solve_alignment_graph(["room_a", "room_b"], [{"target": "room_a", "source": "room_b", "transform": _translation(4.0, 0.0).tolist()}])
    assert not missing
    assert np.allclose(transforms["room_a"], np.eye(4))
    global_b = transform_room_to_global(_room("room_b"), transforms["room_b"])
    assert min(point.x for point in global_b.polygon) == 4.0


def test_doorway_style_boundary_adjacency(tmp_path: Path) -> None:
    """Reuse Stage 6.1 proximity adjacency after evidence places rooms on a shared boundary."""
    result = assemble_stitched_property("property", {"room_a": _room("room_a"), "connector_01": _room("connector_01", 2.0, 1.0)}, [{"target": "room_a", "source": "connector_01", "transform": _translation(4.0, 1.0).tolist(), "fitness": 0.8}], tmp_path)
    assert result["status"] == "PROVISIONAL"
    assert result["adjacency_edges"] == 1
    assert (tmp_path / "property.json").exists()


def test_impossible_overlap_is_not_evaluable(tmp_path: Path) -> None:
    """Reject two independently reconstructed rooms placed in the same physical footprint."""
    result = assemble_stitched_property("overlap", {"room_a": _room("room_a"), "room_b": _room("room_b")}, [{"target": "room_a", "source": "room_b", "transform": np.eye(4).tolist(), "fitness": 0.9}], tmp_path)
    assert result["status"] == "PROPERTY_STITCH_NOT_EVALUABLE"
    assert "impossible_room_overlap" in result["failure_reasons"]


def test_ambiguous_disconnected_property_is_not_evaluable(tmp_path: Path) -> None:
    """Return NOT_EVALUABLE rather than arranging rooms by folder/name order."""
    result = assemble_stitched_property("ambiguous", {"room_a": _room("room_a"), "room_b": _room("room_b")}, [], tmp_path)
    assert result["status"] == "PROPERTY_STITCH_NOT_EVALUABLE"
    assert result["unaligned_rooms"]
