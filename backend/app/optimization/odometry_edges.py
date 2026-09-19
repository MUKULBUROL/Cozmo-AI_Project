"""Stage 6 Sequential Odometry Edge Construction.

1. Why this file exists:
    Constructs rigid relative transformation constraints between chronologically consecutive
    keyframe nodes in the pose graph according to Open3D conventions.

2. Pipeline stage:
    Stage 6 — Sequential Odometry Constraints.

3. Inputs:
    List of KeyframeNode objects containing world poses T_world_cam.

4. Outputs:
    List of OdometryEdge instances defining relative transformations and information matrices.

5. Coordinate conventions:
    Open3D PoseGraph convention:
    An edge connecting node i (source) to node j (target) stores transformation T_ij = inv(T_j) @ T_i,
    which maps 3D points from the coordinate frame of node i to node j.

6. Unit assumptions:
    Translation in meters (m), rotations in radians.

7. Important dependencies:
    numpy, backend.app.optimization.keyframes.

8. What is most likely to break:
    Matrix inversion direction (inv(T_i) @ T_j vs inv(T_j) @ T_i).
    The correct verified formula is inv(T_j) @ T_i.

9. What a developer should inspect first:
    Verify edge translation magnitude matches Euclidean distance between keyframe centers.
"""

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from backend.app.optimization.keyframes import KeyframeNode


@dataclass
class OdometryEdge:
    """Represents a directional edge constraint in the SLAM pose graph.

    Attributes:
        source_node_id: Index of source keyframe node i.
        target_node_id: Index of target keyframe node j.
        transformation: 4x4 matrix mapping points from frame i to frame j: inv(T_j) @ T_i.
        information: 6x6 positive semi-definite information matrix (inverse covariance).
        uncertain: Flag indicating whether edge should be robustly down-weighted.
        distance_meters: Euclidean distance between node centers.
    """
    source_node_id: int
    target_node_id: int
    transformation: np.ndarray
    information: np.ndarray
    uncertain: bool = False
    distance_meters: float = 0.0


def compute_relative_transform(T_world_i: np.ndarray, T_world_j: np.ndarray) -> np.ndarray:
    """Computes relative transformation matrix from frame i to frame j.

    Purpose:
        Calculates T_ij = inv(T_j) @ T_i strictly adhering to Open3D PoseGraph convention.

    Parameters:
        T_world_i: 4x4 homogeneous transformation matrix of source node i (camera-to-world).
        T_world_j: 4x4 homogeneous transformation matrix of target node j (camera-to-world).

    Returns:
        4x4 homogeneous matrix T_ij where P_j = T_ij @ P_i.

    Assumptions:
        Matrices are valid rigid SE(3) transformations (orthonormal rotation).

    Failure conditions:
        Singular matrices raise LinAlgError on inversion.

    Debugging:
        Check that T_ij[:3, :3] has determinant approximately +1.0.
    """
    T_j_inv = np.linalg.inv(T_world_j)
    T_rel = T_j_inv @ T_world_i
    return T_rel.astype(np.float64)


def compute_sequential_odometry_edges(
    keyframes: List[KeyframeNode],
    odometry_weight: float = 1.0,
) -> List[OdometryEdge]:
    """Builds odometry edges connecting consecutive keyframe nodes (0->1, 1->2, ...).

    Purpose:
        Forms the rigid backbone of the pose graph reflecting ARKit's high-frequency VIO.

    Parameters:
        keyframes: List of KeyframeNode objects chronologically sorted.
        odometry_weight: Scalar multiplier for the 6x6 information matrix diagonal.

    Returns:
        List of OdometryEdge objects with sequential constraints.

    Assumptions:
        Keyframes are ordered by time and continuous without missing links.

    Failure conditions:
        Returns empty list if fewer than 2 keyframes are supplied.

    Debugging:
        Verify len(edges) == len(keyframes) - 1.
    """
    if len(keyframes) < 2:
        return []

    edges: List[OdometryEdge] = []
    # Standard identity information matrix weighted by confidence
    info_matrix = np.eye(6, dtype=np.float64) * odometry_weight

    for i in range(len(keyframes) - 1):
        node_i = keyframes[i]
        node_j = keyframes[i + 1]

        T_rel = compute_relative_transform(node_i.matrix, node_j.matrix)
        dist = float(np.linalg.norm(node_j.matrix[:3, 3] - node_i.matrix[:3, 3]))

        edge = OdometryEdge(
            source_node_id=node_i.node_id,
            target_node_id=node_j.node_id,
            transformation=T_rel,
            information=info_matrix.copy(),
            uncertain=False,
            distance_meters=dist,
        )
        edges.append(edge)

    return edges
