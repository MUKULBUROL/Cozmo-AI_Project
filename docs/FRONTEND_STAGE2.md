# COZMO Frontend Stage 2 — Spatial Pro Product UI + Property Workspace

## 1. Executive Summary

Cozmo Frontend Stage 2 establishes the core spatial analysis workspace for the Cozmo AI Project. It implements the **Spatial Pro** design theme and turns the **FLOOR PLAN** into the primary product surface.

All displayed properties originate from **real backend artifacts** (Stages 0–11). No measurements or geometries are fabricated. Where measurements are missing, they are honestly displayed as `Not available`. Status indicators preserve real-world confidence: Video Stage 11 remains strictly `PROVISIONAL`, and failed tracks reflect `NOT_EVALUABLE` status with exact backend failure reasons.

---

## 2. Architecture & Tech Stack

- **Framework**: Next.js 16 (App Router, Turbopack, TypeScript).
- **Styling**: Vanilla CSS using CSS Variables (`tokens.css`, `globals.css`). No Tailwind CSS, no UI bloat.
- **Floor Plan Engine**: 100% native SVG renderer with dynamic viewBox, auto-fit padding, aspect-ratio preservation, and deterministic zoom/pan math. No WebGL/Three.js.
- **Validation**: Zod runtime schema validation for backend JSON contracts.
- **Testing**: Built-in Node test runner (`node --test`) executing unit tests for geometry, bounding boxes, viewBox calculations, and domain adapters.

```
frontend/
├── scripts/
│   └── sync-fixtures.mjs           # Deterministic fixture sync from outputs/
├── tests/
│   ├── geometry.test.mjs           # Bounds & viewBox unit tests
│   └── adapters.test.mjs           # Adapter normalization & data integrity tests
└── src/
    ├── app/
    │   ├── layout.tsx              # Root layout with Geist & Geist Mono fonts
    │   ├── page.tsx                # Property workspace directory
    │   ├── new/page.tsx            # New capture setup (Stage 3 preview)
    │   └── property/[id]/page.tsx  # Main spatial workspace route
    ├── styles/
    │   ├── tokens.css              # Spatial Pro design tokens
    │   └── globals.css             # Resets & responsive grid utilities
    ├── domain/
    │   ├── types.ts                # Strongly typed ViewModels
    │   ├── schemas.ts              # Zod validation schemas
    │   └── adapters.ts             # Backend JSON -> ViewModel normalization
    ├── geometry/
    │   ├── bounds.ts               # Bounding box & extents calculation
    │   ├── viewbox.ts              # Dynamic SVG viewBox math & padding
    │   └── polygon.ts              # SVG path generation & centroid calculation
    ├── data/
    │   ├── generated/              # Synced JSON artifacts (5 scenarios + manifest)
    │   └── fixture-loader.ts       # Fixture loading and scenario catalogue
    └── components/
        ├── layout/
        │   ├── AppShell.tsx        # 3-pane responsive desktop/tablet/mobile layout
        │   ├── TopBar.tsx          # Navigation header with tier and status badges
        │   ├── SideNavigation.tsx  # Left sidebar (Overview, Rooms, Damage, Scope)
        │   └── ViewSwitcher.tsx    # Bottom mode bar + disabled Stage 3 export button
        ├── floorplan/
        │   ├── FloorPlanCanvas.tsx # Native SVG interactive floor plan
        │   └── CanvasControls.tsx  # Zoom (+/-) and Fit view controls
        ├── inspector/
        │   └── InspectorPanel.tsx  # Selected room metrics, walls, and defect scope
        └── ui/
            ├── StatusBadge.tsx     # Complete, Provisional, Not Evaluable, Failed
            ├── TierBadge.tsx       # LiDAR, Video, Photos
            ├── MeasurementStatus.tsx # Mandatory physical accuracy disclaimer
            └── EmptyState.tsx      # Diagnostic failure and missing data cards
```

---

## 3. Design System & Theme: Spatial Pro

- **Mode**: Light mode default.
- **Color Tokens**:
  - `--background`: `#F7F7F5`
  - `--surface`: `#FFFFFF`
  - `--surface-subtle`: `#F3F3F0`
  - `--text-primary`: `#161616`
  - `--text-secondary`: `#737373`
  - `--text-muted`: `#9A9A95`
  - `--border`: `#E6E6E3`
  - `--border-strong`: `#D6D6D2`
  - `--primary`: `#4F46E5`
  - `--primary-hover`: `#4338CA`
  - `--success`: `#22C55E`
  - `--warning`: `#F59E0B`
  - `--danger`: `#EF4444`
  - `--canvas-background`: `#FFFFFF`
- **Border Radii**: 6–10px.
- **Styling Rules Enforced**:
  - No purple AI blobs or decorative AI graphics.
  - No glassmorphism or glowing effects.
  - No generic bright red/green/blue hex scatter.
  - Technical monospace numerals (`Geist Mono`) for all dimensions and areas.

---

## 4. Routes

1. **`/` (Home Workspace)**:
   - Lists available reconstruction captures with tier, status, room count, and floor area.
   - Links directly into individual interactive property workspaces.
2. **`/new` (New Capture Setup)**:
   - Visual tier selector (LiDAR, Video SfM, Photos).
   - Clear indicators that live upload and FastAPI integration arrive in Stage 3.
3. **`/property/[id]` (Interactive Property Workspace)**:
   - Main Stage 2 experience.
   - Full 3-pane layout: Left Navigation (220px), SVG Floor Plan Canvas (flexible center), Right Inspector (320px), and Bottom View Switcher.

---

## 5. Connected Backend Fixtures

| Fixture ID | Backend Source Path | Tier | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| `c7d28f72c6` | `outputs/c7d28f72c6/property/property.json` | LiDAR | `COMPLETE` | 4-room optimized residential property with shared walls and negative coordinates. |
| `c00a170fe1` | `outputs/c00a170fe1/` | LiDAR | `PROVISIONAL` | Single-room scan with closed polygon, doorway openings, water stain defect, and Stage 9 repair scope. |
| `stage11-video` | `outputs/fix_loop/stage11_video/after/property.json` | Video | `PROVISIONAL` | Multi-room video SfM recovery (31/40 views). Strictly preserved as `PROVISIONAL`. |
| `video-multi-room-failure` | `outputs/video_multi_room/video/property/property.json` | Video | `NOT_EVALUABLE` | Sparse drift failure (<30% registration). Renders clean empty state with 3 failure reasons. |
| `photo-property-failure` | `outputs/photo_property_01/photo/property/property.json` | Photos | `NOT_EVALUABLE` | Uncalibrated photo property failure state. |

---

## 6. Commands

Navigate to `frontend/`:

```bash
cd frontend
```

### 1. Synchronize Real Backend Fixtures
Copies and normalizes approved JSON outputs from `outputs/` into `src/data/generated/`:
```bash
npm run fixtures:sync
```

### 2. Run Test Suite
Executes unit tests for bounding boxes, SVG viewBox calculation, and backend adapters:
```bash
npm test
```

### 3. Typecheck
Validates strict TypeScript types across the codebase:
```bash
npm run typecheck
```

### 4. Lint
Runs ESLint:
```bash
npm run lint
```

### 5. Production Build
Compiles optimized static and server-rendered production bundle:
```bash
npm run build
```

### 6. Development Server
Starts Next.js local development server:
```bash
npm run dev
```

---

## 7. Known Limitations & Next Steps

1. **Stage 3 Scope**: Live FastAPI upload, WebSocket progress tracking, and DXF/PDF export will be connected in Frontend Stage 3.
2. **Ground Truth Calibration**: Physical cm-level accuracy is awaiting independent laser ground truth benchmarks; the mandatory notice banner informs users transparently across all views.
