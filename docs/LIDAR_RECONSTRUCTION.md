# LiDAR Reconstruction Guide: From Depth to Metric 3D

This guide explains how CosmoAI converts raw iPhone LiDAR sensor captures into a metric 3D point cloud of an architectural space. It is written conceptually for anyone seeking to understand the physical and mathematical principles behind the reconstruction pipeline.

---

## 1. What Depth Data Represents
Ordinary photos record RGB color (light reflected off surfaces) but lack information on how far away those surfaces are.
An iPhone Pro equipped with LiDAR emits pulsed near-infrared light waves and measures their Time of Flight (ToF) back to the sensor.
- The output is a **2D depth map** ($256 \times 192$ pixels).
- In our raw dataset, depth is stored as a 16-bit unsigned integer (`uint16`) in **millimeters** ($1\text{ mm} = 0.001\text{ m}$).
- For instance, a pixel value of `2450` represents a physical surface exactly $2.45\text{ meters}$ away from the camera along the optical axis.

---

## 2. What Camera Intrinsics Do
Camera intrinsics describe the internal optical geometry of the camera lens and sensor. They map 3D rays in the real world onto 2D pixel coordinates $(u, v)$ on the sensor.
The intrinsic matrix is represented as:
$$K = \begin{bmatrix} f_x & 0 & c_x \\ 0 & f_y & c_y \\ 0 & 0 & 1 \end{bmatrix}$$
- **Focal Lengths ($f_x, f_y$)**: The optical magnification of the lens measured in pixels.
- **Principal Point ($c_x, c_y$)**: The pixel coordinate where the camera's optical axis pierces the image sensor (approximately the center of the image).

Because the RGB camera has a resolution of $1920 \times 1440$ while the LiDAR depth sensor operates at $256 \times 192$, the intrinsic parameters must be scaled proportionally:
$$s_x = \frac{256}{1920}, \quad s_y = \frac{192}{1440}$$
$$f_{x,\text{depth}} = f_{x,\text{rgb}} \cdot s_x, \quad c_{x,\text{depth}} = c_{x,\text{rgb}} \cdot s_x$$

---

## 3. How a 2D Depth Pixel Becomes a 3D Point (Unprojection)
Given a pixel at column $u$ and row $v$ with a depth measurement $d$ in millimeters:
1. **Convert to Metric Distance**:
   $$Z_{\text{camera}} = \frac{d}{1000.0} \quad (\text{meters})$$
2. **Reverse the Pinhole Perspective**:
   Using similar triangles:
   $$X_{\text{camera}} = \frac{(u - c_x) \cdot Z_{\text{camera}}}{f_x}$$
   $$Y_{\text{camera}} = \frac{(v - c_y) \cdot Z_{\text{camera}}}{f_y}$$
This yields a 3D coordinate $P_{\text{camera}} = [X_{\text{camera}}, Y_{\text{camera}}, Z_{\text{camera}}]^T$ located in the camera's local coordinate frame.

---

## 4. Why Camera Poses are Required
A depth frame taken from one position only describes what the camera saw at that exact instant. If the user walks around the room, every new frame has its own independent camera frame.
- **Camera Pose ($T_{\text{world}\leftarrow\text{camera}}$)**: Describes where the camera was located in the room and what angle it was pointing at during that exact frame.
- The pose consists of a **Translation vector** $t = [x, y, z]^T$ (meters) and a **Rotation matrix** $R$ (computed from the orientation quaternion $[q_x, q_y, q_z, q_w]$).

---

## 5. Why All Frames Need a Shared World Coordinate System
To reconstruct an entire room or property, every point observed across thousands of frames must be mapped into **one common coordinate frame**:
$$P_{\text{world}} = R \cdot P_{\text{camera}} + t$$
In Apple ARKit's coordinate system:
- **$+Y$ is vertical (pointing UP)**: Confirmed by the IMU accelerometer registering gravity reaction force along $-Y$.
- **$+X$ and $+Z$ form the horizontal ground plane**: Defining the room's floor footprint.

Once transformed into this shared world frame, points from all frames align to reveal the continuous walls, floors, and openings of the building.

---

## 6. Why Confidence Filtering is Used
LiDAR sensors suffer from noise, especially around object silhouettes, reflective materials (glass, mirrors), or surfaces viewed at steep angles.
Apple ARKit outputs an 8-bit confidence map ($256 \times 192$) alongside every depth map:
- `0` = Low confidence (specular reflections, distant returns, edge scatter).
- `1` = Medium confidence.
- `2` = High confidence (solid diffuse surfaces such as drywall, wood, and concrete).

By filtering out points where $\text{confidence} < 2$, we eliminate phantom floating points and edge spray without discarding real architectural geometry.

---

## 7. Why Voxel Downsampling is Needed
Processing a 3-minute video at 60 FPS generates over 10,000 frames. If each depth frame has 49,152 pixels, raw concatenation would produce **hundreds of millions of points**, consuming gigabytes of RAM and overwhelming downstream geometry algorithms.
- **Voxel Downsampling**: Subdivides 3D space into a grid of small cubes (voxels, e.g. $2\text{ cm} \times 2\text{ cm} \times 2\text{ cm}$).
- All points falling inside a single voxel are averaged into a single centroid point.
- This reduces point redundancy by over $90\%$, balances density between areas scanned multiple times, and preserves sharp wall edges and metric accuracy.

---

## 8. What Trajectory Drift Means
Apple ARKit tracks phone movement using **Visual-Inertial Odometry (VIO)**, fusing high-rate IMU accelerometers with visual feature tracking.
- While VIO is highly accurate frame-to-frame, minute integration errors accumulate over time.
- If a user walks around a large apartment for 3.5 minutes and returns to the starting doorway, the tracked trajectory may show a start-to-end offset (e.g. **$38.9\text{ cm}$ in `single_scan_with_ceiling`**).
- This error is called **trajectory drift**.
- If left uncorrected, walls from the beginning of the walkthrough and walls from the end will not line up, resulting in "ghost" or doubled walls.
- In Stage 1, we measure and document this drift honestly as a baseline. In subsequent stages, Pose Graph Optimization (PGO) and loop closure distribute this error evenly across the loop.

---

## 9. Current Known Limitations
1. **No Ground Truth Room Measurements**: Visual inspection confirms clear walls and floor boundaries, but exact metric accuracy cannot be certified without external laser reference measurements.
2. **Ceiling Incompleteness in Floor-Only Scans**: In `single_scan_floor_only`, the user kept the phone aimed horizontally or downward; ceiling height can only be measured in `single_scan_with_ceiling` and `single_room`.
3. **Drift in Raw Odometry**: Multi-room scans exhibit up to $38.9\text{ cm}$ loop error until pose-graph optimization is integrated.
