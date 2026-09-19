# Structural Extraction Guide: Floor, Ceiling, and Wall Detection

This guide explains how CosmoAI identifies the major structural planes of a room (floor, ceiling, and walls) from a metric 3D point cloud, while rejecting furniture clutter and handling incomplete scans.

---

## 1. What a Plane Is
In 3D geometry, a flat architectural surface (such as a drywall partition or hardwood floor) is modeled mathematically as an infinite plane defined by:
$$a x + b y + c z + d = 0$$
- The vector $\vec{n} = [a, b, c]^T$ is the **surface normal** (a vector sticking perpendicular out of the surface).
- When $\vec{n}$ is normalized so that $a^2 + b^2 + c^2 = 1$, the parameter $|d|$ represents the perpendicular distance from the coordinate origin $(0, 0, 0)$ to the plane.

---

## 2. What a Surface Normal Is
A surface normal is a small arrow at every 3D point indicating which direction the local surface is facing:
- By looking at a point's nearest neighbors (e.g. 30 neighbors within $10\text{ cm}$), we fit a small tangent disk to find the orientation of the surface at that spot.
- **Horizontal surfaces** (floors and ceilings) have normals pointing almost entirely straight up or down along the vertical axis ($\vec{n} \approx [0, \pm 1, 0]$).
- **Vertical surfaces** (walls) have normals that are perpendicular to the vertical axis, meaning their vertical component is near zero ($|n_y| \approx 0$).

---

## 3. What RANSAC Does
Real-world point clouds contain millions of points mixed with noise, furniture, door frames, and shadows.
**RANSAC (RANdom SAmple Consensus)** is a robust algorithm designed to find dominant mathematical shapes even when most points belong to other objects:
1. It randomly picks 3 points and defines a candidate plane through them.
2. It measures how many other points in the cloud lie within a small tolerance (e.g. $3.5\text{ cm}$) of this candidate plane. These matching points are called **inliers**.
3. It repeats this trial hundreds of times and keeps the plane with the largest consensus of inliers.
4. Once the largest plane is found, its inliers are extracted, and RANSAC runs again on the remaining points to find the next structural plane.

---

## 4. How the Floor is Identified
1. We filter all points whose surface normals point vertically ($|n_y| \ge 0.85$).
2. We run RANSAC to detect dominant horizontal planes.
3. Because the floor is the foundation of the room, it corresponds to the **lowest dominant horizontal plane** with massive support (typically $> 50,000$ inliers in our scans).
4. Its normal is aligned to point straight up ($+Y$).

---

## 5. How the Ceiling is Identified
1. We inspect horizontal planes located significantly above the detected floor ($\Delta Y \ge 1.8\text{ m}$).
2. The dominant upper horizontal surface is identified as the ceiling.
3. **Honest Handling of Incomplete Scans**: If the user walked through the room holding the phone at chest height without panning upward toward the ceiling, the scan will contain zero ceiling points. Rather than hallucinating an imaginary ceiling, the algorithm reports `ceiling_detected: false` with the explicit diagnostic reason: `"Insufficient upper horizontal points observed in scan"`.

---

## 6. How Walls are Identified
1. Points assigned to the floor and ceiling are removed.
2. From the remaining points, we select those with vertical surface normals ($|n_y| \le 0.25$).
3. Iterative RANSAC segments large vertical plane candidates.
4. Each candidate must pass structural heuristic gates (described below) before being accepted as a true architectural wall.

---

## 7. Why Furniture Can Create False Planes
Large pieces of furniture (wardrobes, kitchen islands, refrigerators, bed headboards, closed cabinet doors) present large flat surfaces that look mathematically like vertical planes to RANSAC.
To reject furniture clutter, we apply geometric heuristics:
- **Height Span Filter**: True architectural walls span from near the floor to high up in the room ($> 0.70\text{ m}$ vertical span). Short planes (coffee tables, low cabinets) are rejected.
- **Floor Proximity Filter**: Hanging wall cabinets, floating mirrors, or artwork start $1.0\text{ m}$ above the floor; real structural walls extend all the way down to within $0.30\text{ m}$ of the floor plane.
- **Horizontal Extent**: Partition edges or chair backs narrower than $0.70\text{ m}$ are rejected.

---

## 8. Why Duplicate Wall Planes May Appear
When a long wall is partially occluded by furniture or broken up into separate view segments, RANSAC often fits multiple separate planes to different parts of the same physical wall.
- **Parallel Wall Merging**: We compare pairs of wall candidates. If two planes have nearly identical normal vectors (angular difference $< 12^\circ$) and their offset distances $|d_1 - d_2|$ are within $18\text{ cm}$, they are recognized as fragments of the same continuous wall.
- Their inliers are combined, and a single, unified plane equation is refitted.

---

## 9. What Residual and Error Mean
- **Mean Residual**: The average absolute distance from all inlier points to the fitted plane. In our scans, typical wall and floor residuals are between $8\text{ mm}$ and $14\text{ mm}$ ($0.008\text{ m}$–$0.014\text{ m}$).
- **RMSE (Root-Mean-Squared Error)**: Measures the dispersion of points around the plane, penalizing outliers.
- **Confidence Score**: Derived from both the physical point support and the fitting RMSE. A plane supported by 40,000 points with an RMSE of $1.1\text{ cm}$ achieves $> 0.90$ confidence.

---

## 10. Current Limitations
1. **Curved or Non-Planar Walls**: The algorithm assumes standard planar walls; circular or curved walls are not modeled at this stage.
2. **Heavy Clutter Occlusion**: If a wall is almost completely covered from floor to ceiling by floor-to-ceiling storage, inlier density may fall below the detection threshold.
3. **2D Boundaries**: Stage 2 identifies 3D infinite plane equations. Bounding wall lines, corners, room polygons, and door openings are solved in Stage 3.
