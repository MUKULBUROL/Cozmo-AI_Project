# Cozmo Spatial Pro Frontend — Data Contract Specification

- **Stage**: Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
- **Status**: Active / Enforced
- **Purpose**: Defines the exact data contract between backend reconstruction artifacts (Stages 0–11) and the frontend normalization layer.

---

## 1. Executive Summary & Principles

1. **Zero Invented Measurements**: The frontend must never display placeholder or hardcoded default numbers (e.g. defaulting ceiling height to 2.45 m). If an artifact omits a measurement, the UI explicitly renders `Not available`.
2. **Honest Confidence & Calibration**: Confidence intervals (e.g. `[min, max]`) must never be misrepresented as verified physical ground-truth accuracy. An explicit disclaimer is required.
3. **Strict Status Fidelity**: Backend status values (`COMPLETE`, `PROVISIONAL`, `NOT_EVALUABLE`, `FAILED`) must be mirrored verbatim. Video Stage 11 outputs are explicitly `PROVISIONAL`.
4. **Coordinate Robustness**: Geometry coordinates originate in metric Cartesian coordinates (meters) from ARKit or SfM. Coordinates can be negative, non-origin-centered, or inverted in Y/Z depending on camera orientation.

---

## 2. Audited Backend Artifacts

### 2.1 Multi-Room Property (`property.json`)

- **Primary Source Path**: `outputs/c7d28f72c6/property/property.json`
- **Other Sources**: `outputs/fix_loop/stage11_video/after/property.json`
- **Units**: Meters (m) for lengths and coordinates, Square meters (m²) for areas.
- **Coordinate Frame**: `ARKit Y-up, right-handed (XZ horizontal floor)` or metric SfM coordinates. Floor plan 2D projection uses horizontal (X, Y) plane.

#### Schema Breakdown:
- `property_id`: string (e.g. `"prop_c7d28f72c6"`)
- `capture_id`: string (e.g. `"c7d28f72c6"`)
- `tier`: `"lidar" | "video" | "photo"`
- `rooms`: Array of Room objects (see below)
- `connections`: Array of `{ room_a_id, room_b_id, is_shared_wall, shared_wall_length_meters }`
- `total_floor_area`: `{ value, unit, interval: [min, max], confidence, method }`
- `exterior_footprint`: object or `null`
- `reconstruction_method`: string (e.g. `"arkit_lidar_pose_graph_optimized"`)
- `stitching_residual_meters`: number (e.g. `0.0033`)

#### Room Schema (`Room`):
- `room_id`: string (e.g. `"room_01"`)
- `name`: string (e.g. `"Room 01"`, `"Hallway Connector"`)
- `floor_area`: `{ value, unit, interval: [min, max], confidence, method }`
- `perimeter`: `{ value, unit, interval: [min, max], confidence, method }`
- `ceiling_height`: `{ value, unit, interval: [min, max], confidence, method }` or `null`
- `walls`: Array of Wall objects
- `openings`: Array of Opening objects
- `damage_regions`: Array of Damage objects

#### Wall Schema (`Wall`):
- `wall_id`: string (e.g. `"room_01_w01"`)
- `start`: `{ x: number, y: number }` (meters)
- `end`: `{ x: number, y: number }` (meters)
- `length`: `{ value, unit, interval: [min, max], confidence, method }`
- `thickness`: `{ value, unit, interval: [min, max], confidence, method }` or `null`
- `height`: `{ value, unit, interval: [min, max] }` or `null`
- `openings`: Array of attached openings

---

### 2.2 Single-Room Floor Plan Polygon (`room_polygon.json`)

- **Primary Source Path**: `outputs/c00a170fe1/floorplan_geometry/room_polygon.json`
- **Units**: Meters (m) for coordinates, Square meters (m²) for area.

#### Schema Breakdown:
- `scan_id`: string (e.g. `"c00a170fe1"`)
- `coordinate_system`: string
- `polygon`:
  - `vertices`: Array of `[number, number]` (ordered 2D coordinate pairs forming closed boundary)
  - `closed`: boolean
  - `valid`: boolean
  - `area_sqm`: number
  - `perimeter_m`: number
  - `corner_ids`: Array of strings
  - `wall_ids`: Array of strings
- `walls`: Array of `{ wall_id, start: [x, y], end: [x, y], length_m }`
- `corners`: Array of `{ corner_id, point: [x, y], wall_ids: [string, string] }`

---

### 2.3 Measurements Summary (`measurements.json`)

- **Primary Source Path**: `outputs/c00a170fe1/measurements/measurements.json`
- **Units**: Meters (m), m².

#### Schema Breakdown:
- `scan_id`: string
- `status`: `"complete" | "provisional" | "invalid"`
- `status_reasons`: Array of strings
- `floor_area`: `{ value, unit, interval: [min, max], confidence, method }`
- `perimeter`: `{ value, unit, interval: [min, max], confidence, method }`
- `ceiling_height`: `{ value, unit, interval: [min, max], confidence, method }` or `null`
- `ceiling_status`: `"observed" | "not_observed" | "indeterminate"` (When `not_observed`, ceiling_height is null)
- `walls`: Array of `{ wall_id, length_m, uncertainty_m, confidence }`

---

### 2.4 Openings & Doorways (`openings.json`)

- **Primary Source Path**: `outputs/c00a170fe1/openings/openings.json`
- **Units**: Meters (m).

#### Schema Breakdown:
- `scan_id`: string
- `openings_count`: number
- `calibration_status`: string (e.g. `"awaiting_ground_truth_benchmark"`)
- `openings`: Array of:
  - `id`: string (e.g. `"opening_01"`)
  - `type`: `"doorway" | "window" | "pass_through"`
  - `wall_id`: string
  - `status`: `"accepted" | "provisional" | "rejected"`
  - `width`: `{ value, unit, interval: [min, max], half_width_uncertainty_m, confidence, calibrated }`
  - `left_jamb_3d`: `[x, y, z]` (meters)
  - `right_jamb_3d`: `[x, y, z]` (meters)
  - `centroid_3d`: `[x, y, z]` (meters)
  - `calibrated`: boolean
  - `detector_confidence`: number

---

### 2.5 Damage Detections & Repair Scope (`damages.json`, `repair_scope.json`)

- **Primary Source Paths**: `outputs/c00a170fe1/damage/damages.json`, `outputs/c00a170fe1/damage/repair_scope.json`, `outputs/c00a170fe1/damage/damage_summary.json`

#### Damage Schema:
- `damage_id`: string (e.g. `"dmg_c00a170fe1_01"`)
- `damage_class`: `"water_stain" | "crack_structural" | "mold" | "impact"`
- `class_confidence`: number (0.0 to 1.0)
- `host_surface_id`: string (e.g. `"wall_01"`)
- `host_surface_type`: `"wall" | "ceiling" | "floor"`
- `metric_area`: `{ value, unit, interval: [min, max], confidence }` or `null`
- `metric_length`: `{ value, unit, interval: [min, max], confidence }` or `null`
- `status`: `"ACCEPTED" | "PROVISIONAL" | "NOT_EVALUABLE"`
- `concealed_flags`: Array of:
  - `rule_id`: string
  - `suspected_issue`: string
  - `requires_inspection`: boolean
  - `inspection_recommendation`: string

#### Scope Schema (`repair_scope.json` - Array of Line Items):
- `line_item_id`: string
- `damage_id`: string
- `action`: string (remediation/repair description)
- `target_surface`: string
- `quantity`: number
- `unit`: `"inspection" | "m2" | "linear_m"`
- `basis`: string
- `confidence`: number
- `inspection_required`: boolean

---

### 2.6 Video Failure & Provisional States (`property.json`, `comparison.json`)

- **Primary Source Path (Provisional Video)**: `outputs/fix_loop/stage11_video/after/property.json` + `comparison.json`
  - Registered views: 31/40 (77.5%)
  - Status: **`PROVISIONAL`** (Must not be converted to Complete)
- **Primary Source Path (Failure State)**: `outputs/video_multi_room/video/property/property.json`
  - Status: **`NOT_EVALUABLE`**
  - Failure reasons: `["only_4_registered_views_minimum_20", "registration_ratio_0.100_below_0.30", "largest_registered_time_gap_106.066s_exceeds_continuity_limit"]`
  - Rooms: `[]` (Empty geometry)

---

## 3. Frontend Normalization Layer Architecture

```
Backend Artifacts (JSON)
        │
        ▼
[Zod Schemas / Safe Parsers]
        │
        ▼
[Domain Adapters] (normalizeProperty, normalizeRoomPolygon)
        │
        ▼
[Frontend ViewModels]
  ├── PropertyViewModel (id, name, tier, status, rooms, bounds, accuracyStatus)
  ├── RoomViewModel (id, name, polygon, walls, area, ceiling, openings, damages)
  ├── WallViewModel (id, start, end, length, labelPosition)
  ├── OpeningViewModel (id, type, wallId, start, end, width, calibrated)
  ├── DamageViewModel (id, class, surface, area, length, concealedFlags, scopeItems)
  └── ScopeItemViewModel (id, action, quantity, unit, inspectionRequired)
        │
        ▼
[React UI Components] (FloorPlanCanvas, InspectorPanel, TopBar)
```
