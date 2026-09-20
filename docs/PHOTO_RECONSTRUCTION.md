# Stage 8 Photo-Only Reconstruction

## Scope

Stage 8 accepts 2-8 ordinary iPhone still photographs per room. It reconstructs camera geometry,
metric depth, metric scale, and a semi-dense point cloud before reusing Stages 2-6. It does not read
video, LiDAR depth, confidence maps, odometry, ARKit poses, or Stage 7 scale/trajectory artifacts.

## Why Photos Are Harder Than LiDAR

LiDAR observes metric depth and ARKit supplies a gravity-aware trajectory. Independent photographs
contain neither. Structure-from-Motion (SfM) can infer relative camera motion and sparse 3D points
from repeated visual features, but the result has an arbitrary global scale and gauge orientation.
Textureless walls, mirrors, glass, exposure changes, and blur all reduce reliable correspondence.

## Why 2-8 Views Are Difficult

Two views can triangulate points, but calibration, baseline, and scene degeneracy are weakly
constrained. Pure rotation produces no translational parallax. A narrow view of one textured object
does not establish room coverage. The pipeline therefore reports registration ratio, reprojection
error, baseline/scene spread, sparse-point distribution, viewpoint diversity, and connected
components. Weak evidence becomes `PROVISIONAL` or `FAILED`; no room polygon is forced.

## Input Contract and EXIF

Single room:

```text
photos/room_01/
  any-name.jpg
  another.jpeg
  view.png
```

Whole property:

```text
photos/property_01/
  room_01/
  room_02/
  room_03/
  connector_01/
```

Direct-child `.jpg`, `.jpeg`, `.png`, `.heic`, and `.heif` names are discovered without a fixed
naming scheme. HEIC works only when the local Pillow installation has a registered HEIF decoder;
otherwise the manifest records a clear decode rejection. EXIF orientation is applied before any
geometry. Original and processing dimensions, orientation transform, timestamp, make/model, focal
length, 35 mm equivalent, and safe EXIF values are retained. Missing EXIF is valid and pycolmap
self-calibration is recorded as the intrinsics source.

Fewer than two decodable photos fail. More than eight are deterministically truncated by casefolded
filename order, and every omitted path is recorded.

## Photo SfM

For 2-8 unordered views, pycolmap extracts SIFT features, exhaustively matches every image pair,
geometrically verifies matches, and runs incremental mapping/bundle adjustment. Temporal adjacency
is never assumed. The largest reconstructed component yields camera intrinsics, world-from-camera
poses, sparse tie points, tracks, and reprojection diagnostics. Two-view results are always marked
poorly constrained even if a sparse model exists.

## Metric Depth and Scale

Registered images run independently through:

```text
depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf
```

Depth arrays are cached in meters. Masks reject non-finite/out-of-range depth and strong depth
discontinuities. Mirrors and glass remain known model failure cases and are handled indirectly by
cross-view disagreement rather than claimed semantic certainty.

SfM scale is recovered from many tracked points. Each arbitrary-scale sparse point is transformed
into its observing camera, projected into the metric depth map, and contributes
`metric_depth / sfm_depth`. Masked pixels cannot contribute. Median/MAD rejection produces the
scale factor, correspondence/inlier counts, MAD, and relative uncertainty. Door width, human height,
room size, ceiling height, LiDAR dimensions, and Stage 7 scale are never scale references.

Only camera translations and sparse-point coordinates are multiplied by scale. Rotations are not
scaled. Deterministic tests protect this convention.

## Metric Cloud and Shared Geometry

The existing Stage 7 pinhole unprojection maps each metric depth image into camera coordinates.
Metric camera poses transform those points to world coordinates. A robust aggregate camera-up cue
rotates the arbitrary SfM gauge into the shared right-handed Y-up frame. An 8 cm multi-view voxel
test records supported and rejected points; weak overlap remains `PROVISIONAL`.

Outputs include:

```text
photo_contact_sheet.jpg
sfm_cameras.svg
scale_consistency.svg
photo_pointcloud_raw.ply
photo_pointcloud_filtered.ply
structure/
floorplan_geometry/floorplan_debug.svg
measurements/dimensioned_debug.svg
```

The filtered cloud is represented by the common `ReconstructionResult` with `tier="photo"`, meters,
camera trajectory, intrinsics provenance, scale status, and confidence evidence. Stage 2 performs
structural extraction, Stage 3 attempts a polygon, and Stage 4 propagates scale, depth, pose, plane,
and corner uncertainty. `uncertainty_calibrated` remains false. Stage 5 semantics are not converted
from boxes to metric dimensions; without local detector weights and valid wall geometry, openings
are `NOT_EVALUABLE`.

## Room-Frame Stitching

Every property child folder is reconstructed independently in a traceable local metric frame.
Connector-to-room metric clouds are exhaustively registered with FPFH/RANSAC and point-to-plane ICP.
Only accepted observed overlap edges enter the alignment graph. Folder names identify records but
never establish order or adjacency. Relative transforms preserve unit scale and contain only
rotation and translation.

The evidence graph is composed into a global property frame. Transformed local polygons then use
the existing Stage 6.1 overlap validation, adjacency inference, property serializer, and debug SVG.
The property output distinguishes observed cloud alignment from topology inferred after placement.

Stitching returns `PROPERTY_STITCH_NOT_EVALUABLE` when:

- fewer than two room polygons are valid;
- connector/shared-cloud registration is weak;
- the alignment evidence graph is disconnected;
- a transform contains scale/reflection;
- transformed rooms overlap impossibly;
- connector evidence cannot determine relative placement.

It never arranges rooms by folder order.

## Synthetic Development Data Limitation

The supplied archives have no genuine assessment-style photo folders. Development stills are
therefore extracted beforehand from RGB video and labeled:

```text
SYNTHETIC DEVELOPMENT PHOTO SET
NOT REAL ASSESSMENT PHOTO CAPTURE
```

The extraction command writes only JPEGs and a provenance manifest. The reconstruction command is
then run against the JPEG directory only. This validates software isolation but does not reproduce
iPhone still-camera EXIF, independent shutter timing, or an assessment capture protocol.

The first six-view whole-video sample produced zero matches. An overlapping local window produced
5/6 registered views. This supports future capture hints: move around corners, preserve overlap,
include textured structural regions and door/connector views, avoid all photos from one position,
and avoid blur, severe darkness, overexposure, mirrors, and glass. This is diagnostic evidence, not
the final capture protocol.

## Commands

Create development stills before reconstruction:

```bash
python3 -m scripts.create_photo_dev_set \
  --archive "sample data/single_room.zip" \
  --scan c00a170fe1 \
  --output data/photo_dev/single_room

python3 -m scripts.create_photo_dev_set \
  --archive "sample data/single_scan_with_ceiling.zip" \
  --scan c7d28f72c6 \
  --output data/photo_dev/property_photo_dev \
  --property
```

Run ordinary photo-only reconstruction:

```bash
python3 -m scripts.reconstruct_photos \
  --input data/photo_dev/single_room \
  --capture-id photo_room_01 \
  --synthetic-development-set

python3 -m scripts.reconstruct_photos \
  --input data/photo_dev/property_photo_dev \
  --capture-id photo_property_01 \
  --synthetic-development-set
```

View the result and compare only after independent reconstruction:

```bash
python3 -m scripts.view_photo_reconstruction \
  --capture-id photo_room_01 \
  --lidar-scan c00a170fe1 \
  --video-capture video_single_room \
  --headless
```

Run tests and dataset validation:

```bash
python3 -m pytest backend/tests
python3 -m scripts.validate_dataset
```

Cross-tier output is labeled `CROSS-TIER AGREEMENT, NOT GROUND-TRUTH ACCURACY`. Tape or laser
ground truth is required before benchmark accuracy can be claimed.
