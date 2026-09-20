# Frontend Stage 3 — Live FastAPI Integration & Spatial Pro Canvas

## 1. Overview

Frontend Stage 3 connects the Next.js Spatial Pro web workspace to a live FastAPI reconstruction backend. Evaluators can upload raw iPhone captures (LiDAR, RGB Video, or Multi-View Photos), monitor processing progress via real-time polling, and inspect fully interactive, dimensioned floor plans with intelligent label collision resolution.

---

## 2. Quickstart & Installation

### Backend Setup (FastAPI)
```bash
# Install Python dependencies (from repository root)
pip install -e ".[dev,viz,photo]"

# Start FastAPI API server on port 8000
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Verify backend health:
```bash
curl http://localhost:8000/health
# Response: {"status":"ok","service":"cozmo-spatial-api"}
```

API Documentation:
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Frontend Setup (Next.js)
```bash
cd frontend

# Install Node dependencies
npm install

# Configure environment (copy example)
cp .env.example .env.local

# Run Next.js development server
npm run dev
```

Frontend application: `http://localhost:3000`

---

## 3. Environment Configuration

The frontend requires `NEXT_PUBLIC_API_BASE_URL` pointing to the FastAPI backend:

```env
# frontend/.env.example & frontend/.env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_DATA_MODE=live
```

> **Security Note**: `frontend/.env.local` is gitignored (`git check-ignore frontend/.env.local`).

---

## 4. Evaluator Workflow & Job Lifecycle

### Upload Flow (`/new`)
1. **Tier Selection**: Choose from LiDAR Reconstruction, RGB Video SfM, or Multi-View Photo Set.
2. **File Selection**: Client-side validation checks extension compatibility (`.zip`, `.mp4`, `.mov`) and provides instant feedback.
3. **Upload**: Submits multipart `FormData` to `POST /api/captures`.
4. **Redirection**: On HTTP 200 receipt with fresh capture ID (`cap_...`), automatically routes to `/processing/<id>`.

### Processing & Polling Flow (`/processing/[id]`)
1. Polls `GET /api/captures/{id}` every 3 seconds.
2. Shows elapsed execution timer, sensor tier badge, and live pipeline stage messages.
3. Automatically halts polling on terminal statuses:
   - `COMPLETE` → Auto-redirects to `/property/<id>`.
   - `PROVISIONAL` → Auto-redirects to `/property/<id>` with provisional banner.
   - `NOT_EVALUABLE` → Displays honest failure reasons and retry action.
   - `FAILED` → Displays diagnostic error message and return action.
4. Cleans up polling timers on unmount; handles network drops with bounded retries.

### Dynamic Property Route (`/property/[id]`)
- Fully dynamic routing without build-time static param limitations.
- Resolves live capture IDs from `GET /api/captures/{id}/result`.
- **Honest Error Handling**: If an API request fails, the page shows a clear error message. Silent fixture fallback is strictly prohibited in live mode.

---

## 5. Floor Plan Viewport UX & Collision Avoidance

### SVG Workspace & Scroll Container
The `FloorPlanCanvas` component is enclosed in a bounded, scroll-safe container with `overflow: auto`. SVG coordinates use real metric units (meters) without WebGL bloat.

### Dimension Collision Resolution (`collision.ts`)
Dense floor plans can cause wall measurements, room names, and floor areas to overlap. The collision avoidance algorithm ensures readability:

1. **Bounding Box Estimation**: Computes axis-aligned bounding rectangles (`LabelRect`) in SVG metric coordinates.
2. **Priority Ordering**:
   - `SELECTED_WALL` (Priority 0): Always visible.
   - `SELECTED_ROOM` (Priority 1): Selected room dimensions take precedence.
   - `ROOM_NAME` (Priority 2): Room titles.
   - `MAJOR_DIMENSION` (Priority 3): Total floor area labels.
   - `OTHER_DIMENSION` (Priority 4): Secondary wall dimensions.
3. **Perpendicular Offset Retries**: If a wall label collides, up to 3 perpendicular offset steps are evaluated.
4. **Graceful Fallback**: If collisions cannot be resolved, lower-priority labels are hidden from the SVG canvas while remaining fully accessible in the Inspector Panel.
5. **Zoom Density Gating**: `getMaxLabelsForZoom(zoom)` dynamically reduces label density at low zoom levels to maintain visual clarity.

### Viewport Controls (`CanvasControls.tsx`)
- **Zoom In / Zoom Out (`+` / `-`)**: Smooth geometric scaling bounded between 25% and 600%.
- **Fit (`0`)**: Fits the entire property geometry within view with 10% architectural padding.
- **Focus Room (`F`)**: Centers the selected room in the viewport with bounded zoom.
- **Mouse & Keyboard Navigation**: Pan with mouse drag, zoom with Ctrl/Cmd + Wheel, arrow key panning.

---

## 6. Validation Summary

### Frontend Verification
```bash
cd frontend
npm run lint       # 0 errors
npm run typecheck  # Passed
npm test           # 51 passed across 11 suites (0 failed)
npm run build      # Static & dynamic routes compiled cleanly
```

### Backend Verification
```bash
python3 -m pytest backend/tests         # 190 passed (0 failed)
python3 -m scripts.validate_dataset     # Dataset validation passed
python3 -m compileall -q backend scripts # Clean compilation
git diff --check                         # 0 whitespace / formatting issues
```

### End-to-End Real Capture Proof
- **Input**: `sample data/single_room.zip` (88,525,307 bytes)
- **SHA-256**: `0805f742d378e4bda480fef6e5839304364807bb7b77bb459983003727e9699c`
- **Generated Capture ID**: `cap_bdc3f329`
- **Storage**: `runtime/captures/cap_bdc3f329/input/single_room.zip` (SHA-256 verified identical)
- **Reconstruction Output**: 17 fresh artifacts generated in `runtime/captures/cap_bdc3f329/outputs/`
- **Execution Time**: 12.71 seconds
- **Result Route**: `/property/cap_bdc3f329` (4 rooms, metric geometry, zero fixture substitution)

---

## 7. Known Limitations

1. **In-Memory Job Queue**: Processing jobs run in asynchronous daemon threads. Job state is persisted to `runtime/captures/<id>/job.json` and restored on startup, but in-flight jobs interrupted by process shutdown must be re-submitted.
2. **Video SfM Runtime**: RGB Video reconstruction with dense feature matching and depth unprojection can take up to 2-3 minutes depending on frame count.
3. **Accuracy Disclaimer**: In compliance with truthfulness standards, all measurement surfaces carry the disclaimer that physical accuracy has not yet been validated against independent laser ground truth.
