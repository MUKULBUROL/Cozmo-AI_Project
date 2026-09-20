# Stage 10 Benchmark: Staged Property Damage Capture Protocol

## Purpose
Establishes a standardized, reproducible field protocol for capturing authentic ground-truth
property damage across LiDAR, Video, and Photo modalities within a controlled interior environment.

## Protocol Requirements
1. **Target Space**:
   - One enclosed, furnished room (minimum 3.0 m × 4.0 m).
   - Clear architectural walls with defined structural planes.

2. **Staged Damage Classes**:
   - **Defect A (Area Type)**: Simulated water stain or surface spall ($1.0\text{ m}^2$ to $1.5\text{ m}^2$).
   - **Defect B (Linear Type)**: Measured hairline / structural crack ($1.0\text{ m}$ to $2.0\text{ m}$).

3. **Ground-Truth Benchmark Measurement**:
   - Measure physical bounding polygon using calibrated laser distance meter (accuracy $\pm 1.5\text{ mm}$).
   - Measure linear crack chord length using steel engineering tape.
   - Record true coordinates in `data/ground_truth/damage_ground_truth.json`.

4. **Multi-Tier Synchronized Capture**:
   - **LiDAR**: Continuous ARKit sweep capturing synchronized RGB + 256x192 depth + 6D poses.
   - **Video**: 4K/60fps continuous walking trajectory with 80% keyframe overlap.
   - **Photo**: Minimum 8 high-resolution stills from multiple viewing angles ($< 45^\circ$ incidence).

5. **Lighting Standards**:
   - Uniform diffuse interior illumination (300–500 lux).
   - Avoid direct specular glares or deep flash cast shadows.
