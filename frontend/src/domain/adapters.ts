/**
 * @file adapters.ts
 * @purpose Normalization layer converting raw backend reconstruction artifacts into frontend domain ViewModels.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Raw JSON backend artifacts (multi-room property, single-room scans, failure outputs).
 * @outputs Fully normalized, strongly-typed PropertyViewModel and RoomViewModel objects.
 * @dependencies ./types, ./schemas, ../geometry/bounds, ../geometry/polygon
 * @assumptions Raw artifacts follow FRONTEND_DATA_CONTRACT.md. Never invents missing values; preserves exact backend status.
 * @failureModes Unrecognized raw JSON shapes safely produce a PropertyViewModel with NOT_EVALUABLE or FAILED status without crashing.
 * @firstDebuggingPoints Inspect raw artifact fields in browser console / adapter logs; check status mapping logic.
 */

import {
  Point2D,
  ValueWithConfidence,
  PropertyViewModel,
  RoomViewModel,
  WallViewModel,
  OpeningViewModel,
  DamageViewModel,
  ScopeItemViewModel,
  ReconstructionTier,
  ReconstructionStatus,
} from './types';
import { computeBoundingBox, unionBoundingBoxes } from '../geometry/bounds';
import { computePolygonCentroid, computeDimensionLabelPosition } from '../geometry/polygon';

/**
 * Standard ground-truth accuracy disclaimer text required across all measurement surfaces.
 */
export const ACCURACY_DISCLAIMER_TEXT =
  'Physical accuracy has not yet been validated against independent laser/tape ground truth.';

/**
 * Maps raw backend value objects to normalized ValueWithConfidence models.
 * 
 * @param raw - Raw value object or number.
 * @param defaultUnit - Unit string if unspecified.
 * @returns Normalized ValueWithConfidence or null if input is absent.
 */
function normalizeValueWithConfidence(
  raw: unknown,
  defaultUnit = 'm'
): ValueWithConfidence | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === 'number') {
    if (isNaN(raw)) return null;
    return { value: raw, unit: defaultUnit };
  }

  if (typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    const val = typeof obj.value === 'number' ? obj.value : null;
    if (val === null || isNaN(val)) return null;

    const unit = typeof obj.unit === 'string' ? obj.unit : defaultUnit;
    const lower = typeof obj.lower_bound === 'number' ? obj.lower_bound : undefined;
    const upper = typeof obj.upper_bound === 'number' ? obj.upper_bound : undefined;

    let interval: [number, number] | undefined = undefined;
    if (Array.isArray(obj.interval) && obj.interval.length === 2) {
      const [i0, i1] = obj.interval;
      if (typeof i0 === 'number' && typeof i1 === 'number') {
        interval = [i0, i1];
      }
    } else if (lower !== undefined && upper !== undefined) {
      interval = [lower, upper];
    }

    const conf = typeof obj.confidence === 'number' ? obj.confidence : undefined;
    const method = typeof obj.method === 'string' ? obj.method : undefined;

    return {
      value: val,
      unit,
      lowerBound: lower,
      upperBound: upper,
      interval,
      confidence: conf,
      method,
    };
  }

  return null;
}

/**
 * Maps arbitrary status string into strict ReconstructionStatus union.
 * 
 * @param rawStatus - Status from backend artifact.
 * @param tier - Reconstruction tier.
 * @param captureId - Unique capture identifier.
 * @returns Strict status: COMPLETE | PROVISIONAL | NOT_EVALUABLE | FAILED.
 */
export function normalizeStatus(
  rawStatus: unknown,
  tier: ReconstructionTier
): ReconstructionStatus {
  // Video Stage 11 must strictly remain PROVISIONAL as required
  if (tier === 'video') {
    if (typeof rawStatus === 'string') {
      const upper = rawStatus.toUpperCase();
      if (upper === 'NOT_EVALUABLE') return 'NOT_EVALUABLE';
      if (upper === 'FAILED') return 'FAILED';
    }
    return 'PROVISIONAL';
  }

  if (typeof rawStatus === 'string') {
    const s = rawStatus.toUpperCase();
    if (s === 'COMPLETE' || s === 'ACCEPTED' || s === 'SUCCEEDED') return 'COMPLETE';
    if (s === 'PROVISIONAL') return 'PROVISIONAL';
    if (s === 'NOT_EVALUABLE') return 'NOT_EVALUABLE';
    if (s === 'FAILED' || s === 'INVALID' || s === 'REJECTED') return 'FAILED';
  }

  // LiDAR outputs without explicit status field default to COMPLETE
  if (tier === 'lidar') {
    return 'COMPLETE';
  }

  // Default to PROVISIONAL for other unknown status — never hardcode by capture ID.
  return 'PROVISIONAL';
}

/**
 * Normalizes a raw wall segment into WallViewModel with label coordinates.
 * 
 * @param rawWall - Raw wall object.
 * @param defaultWallId - Fallback ID if not provided.
 * @returns WallViewModel.
 */
function normalizeWall(rawWall: unknown, defaultWallId: string): WallViewModel {
  const w = (rawWall && typeof rawWall === 'object' ? rawWall : {}) as Record<string, unknown>;
  const id = typeof w.wall_id === 'string' ? w.wall_id : defaultWallId;

  // Extract start point
  let start: Point2D = { x: 0, y: 0 };
  if (w.start && typeof w.start === 'object') {
    if (Array.isArray(w.start) && w.start.length >= 2) {
      start = { x: Number(w.start[0]) || 0, y: Number(w.start[1]) || 0 };
    } else {
      const s = w.start as Record<string, unknown>;
      start = { x: Number(s.x) || 0, y: Number(s.y) || 0 };
    }
  }

  // Extract end point
  let end: Point2D = { x: 0, y: 0 };
  if (w.end && typeof w.end === 'object') {
    if (Array.isArray(w.end) && w.end.length >= 2) {
      end = { x: Number(w.end[0]) || 0, y: Number(w.end[1]) || 0 };
    } else {
      const e = w.end as Record<string, unknown>;
      end = { x: Number(e.x) || 0, y: Number(e.y) || 0 };
    }
  }

  // Length calculation or extraction
  let length = normalizeValueWithConfidence(w.length, 'm');
  if (!length && typeof w.length_m === 'number') {
    length = { value: w.length_m, unit: 'm' };
  }
  if (!length) {
    const computedLen = Math.hypot(end.x - start.x, end.y - start.y);
    length = { value: parseFloat(computedLen.toFixed(3)), unit: 'm' };
  }

  const thickness = normalizeValueWithConfidence(w.thickness, 'm');
  const height = normalizeValueWithConfidence(w.height, 'm');
  const labelPoint = computeDimensionLabelPosition(start, end, 0.15);

  return {
    id,
    start,
    end,
    length,
    thickness,
    height,
    labelPoint,
  };
}

/**
 * Normalizes opening records into OpeningViewModel.
 * 
 * @param rawOpening - Raw opening dictionary.
 * @returns OpeningViewModel.
 */
function normalizeOpening(rawOpening: unknown): OpeningViewModel {
  const o = (rawOpening && typeof rawOpening === 'object' ? rawOpening : {}) as Record<string, unknown>;
  const id = typeof o.id === 'string' ? o.id : 'opening_unknown';
  const type = (typeof o.type === 'string' && ['doorway', 'window', 'pass_through'].includes(o.type)
    ? o.type
    : 'doorway') as 'doorway' | 'window' | 'pass_through';
  const wallId = typeof o.wall_id === 'string' ? o.wall_id : '';
  const status = typeof o.status === 'string' ? o.status : 'provisional';
  const calibrated = typeof o.calibrated === 'boolean' ? o.calibrated : false;
  const width = normalizeValueWithConfidence(o.width, 'm') || { value: 0.9, unit: 'm' };

  let leftJamb: Point2D | undefined = undefined;
  if (Array.isArray(o.left_jamb_3d) && o.left_jamb_3d.length >= 2) {
    leftJamb = { x: o.left_jamb_3d[0], y: o.left_jamb_3d[1] };
  }

  let rightJamb: Point2D | undefined = undefined;
  if (Array.isArray(o.right_jamb_3d) && o.right_jamb_3d.length >= 2) {
    rightJamb = { x: o.right_jamb_3d[0], y: o.right_jamb_3d[1] };
  }

  return {
    id,
    type,
    wallId,
    width,
    status,
    calibrated,
    leftJamb,
    rightJamb,
  };
}

/**
 * Normalizes damage regions and attached remediation scope.
 * 
 * @param rawDamage - Raw damage object.
 * @param globalScope - Optional list of repair scope items.
 * @returns DamageViewModel.
 */
function normalizeDamage(rawDamage: unknown, globalScope?: unknown[]): DamageViewModel {
  const d = (rawDamage && typeof rawDamage === 'object' ? rawDamage : {}) as Record<string, unknown>;
  const id = typeof d.damage_id === 'string' ? d.damage_id : 'dmg_unknown';
  const damageClass = typeof d.damage_class === 'string' ? d.damage_class : 'defect';
  const confidence = typeof d.class_confidence === 'number' ? d.class_confidence : 1.0;
  const hostSurfaceId = typeof d.host_surface_id === 'string' ? d.host_surface_id : 'unassigned';
  const hostSurfaceType = typeof d.host_surface_type === 'string' ? d.host_surface_type : 'wall';
  const status = typeof d.status === 'string' ? d.status : 'ACCEPTED';

  const metricArea = normalizeValueWithConfidence(d.metric_area, 'm2');
  const metricLength = normalizeValueWithConfidence(d.metric_length, 'm');

  const concealedFlags: DamageViewModel['concealedFlags'] = [];
  if (Array.isArray(d.concealed_flags)) {
    for (const flag of d.concealed_flags) {
      if (flag && typeof flag === 'object') {
        const f = flag as Record<string, unknown>;
        concealedFlags.push({
          ruleId: typeof f.rule_id === 'string' ? f.rule_id : 'FLAG',
          suspectedIssue: typeof f.suspected_issue === 'string' ? f.suspected_issue : '',
          requiresInspection: Boolean(f.requires_inspection),
          recommendation: typeof f.inspection_recommendation === 'string' ? f.inspection_recommendation : '',
        });
      }
    }
  }

  const scopeItems: ScopeItemViewModel[] = [];
  const rawItems = Array.isArray(d.scope_line_items) ? d.scope_line_items : [];

  for (const item of rawItems) {
    if (item && typeof item === 'object') {
      const it = item as Record<string, unknown>;
      scopeItems.push({
        id: typeof it.line_item_id === 'string' ? it.line_item_id : 'item',
        damageId: id,
        action: typeof it.action === 'string' ? it.action : '',
        targetSurface: typeof it.target_surface === 'string' ? it.target_surface : '',
        quantity: typeof it.quantity === 'number' ? it.quantity : 1,
        unit: typeof it.unit === 'string' ? it.unit : '',
        basis: typeof it.basis === 'string' ? it.basis : '',
        confidence: typeof it.confidence === 'number' ? it.confidence : 1.0,
        inspectionRequired: Boolean(it.inspection_required),
      });
    }
  }

  // Also match items from global scope if available
  if (Array.isArray(globalScope)) {
    for (const item of globalScope) {
      if (item && typeof item === 'object') {
        const it = item as Record<string, unknown>;
        if (it.damage_id === id && !scopeItems.some((s) => s.id === it.line_item_id)) {
          scopeItems.push({
            id: typeof it.line_item_id === 'string' ? it.line_item_id : 'item',
            damageId: id,
            action: typeof it.action === 'string' ? it.action : '',
            targetSurface: typeof it.target_surface === 'string' ? it.target_surface : '',
            quantity: typeof it.quantity === 'number' ? it.quantity : 1,
            unit: typeof it.unit === 'string' ? it.unit : '',
            basis: typeof it.basis === 'string' ? it.basis : '',
            confidence: typeof it.confidence === 'number' ? it.confidence : 1.0,
            inspectionRequired: Boolean(it.inspection_required),
          });
        }
      }
    }
  }

  return {
    id,
    damageClass,
    confidence,
    hostSurfaceId,
    hostSurfaceType,
    metricArea,
    metricLength,
    status,
    concealedFlags,
    scopeItems,
  };
}

/**
 * Normalizes multi-room property JSON (outputs/c7d28f72c6) into PropertyViewModel.
 * 
 * @param raw - Parsed raw JSON object.
 * @returns PropertyViewModel.
 */
export function normalizeMultiRoomProperty(raw: unknown): PropertyViewModel {
  const data = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;

  const id = typeof data.property_id === 'string' ? data.property_id : 'prop_c7d28f72c6';
  const captureId = typeof data.capture_id === 'string' ? data.capture_id : id;
  const tier: ReconstructionTier =
    data.tier === 'video' ? 'video' : data.tier === 'photo' ? 'photo' : 'lidar';

  const status = normalizeStatus(data.status, tier, captureId);
  const totalFloorArea = normalizeValueWithConfidence(data.total_floor_area, 'm2');
  const reconstructionMethod = typeof data.reconstruction_method === 'string' ? data.reconstruction_method : null;

  const rawRooms = Array.isArray(data.rooms) ? data.rooms : [];
  const rooms: RoomViewModel[] = [];

  for (let rIdx = 0; rIdx < rawRooms.length; rIdx++) {
    const rawR = rawRooms[rIdx] as Record<string, unknown>;
    const roomId = typeof rawR.room_id === 'string' ? rawR.room_id : `room_${rIdx + 1}`;
    const name = typeof rawR.name === 'string' ? rawR.name : `Room ${rIdx + 1}`;

    const rawWalls = Array.isArray(rawR.walls) ? rawR.walls : [];
    const walls: WallViewModel[] = [];
    const polygon: Point2D[] = [];

    for (let wIdx = 0; wIdx < rawWalls.length; wIdx++) {
      const w = normalizeWall(rawWalls[wIdx], `${roomId}_w${wIdx + 1}`);
      walls.push(w);
      polygon.push(w.start);
    }

    const bounds = computeBoundingBox(polygon);
    const center = computePolygonCentroid(polygon);
    const floorArea = normalizeValueWithConfidence(rawR.floor_area, 'm2');
    const perimeter = normalizeValueWithConfidence(rawR.perimeter, 'm');
    const ceilingHeight = normalizeValueWithConfidence(rawR.ceiling_height, 'm');

    const openings: OpeningViewModel[] = [];
    if (Array.isArray(rawR.openings)) {
      for (const op of rawR.openings) {
        openings.push(normalizeOpening(op));
      }
    }

    const damages: DamageViewModel[] = [];
    if (Array.isArray(rawR.damage_regions)) {
      for (const dmg of rawR.damage_regions) {
        damages.push(normalizeDamage(dmg));
      }
    }

    rooms.push({
      id: roomId,
      name,
      polygon,
      bounds,
      center,
      floorArea,
      perimeter,
      ceilingHeight,
      ceilingStatus: ceilingHeight ? 'observed' : 'not_observed',
      walls,
      openings,
      damages,
    });
  }

  const roomBoxes = rooms.map((r) => r.bounds);
  const propertyBounds = unionBoundingBoxes(roomBoxes);

  const failureReasons: string[] = [];
  if (Array.isArray(data.failure_reasons)) {
    for (const f of data.failure_reasons) {
      if (typeof f === 'string') failureReasons.push(f);
    }
  }

  return {
    id,
    captureId,
    name: 'Residential Property (Multi-Room)',
    tier,
    status,
    statusReasons: failureReasons,
    reconstructionMethod,
    totalFloorArea,
    rooms,
    bounds: propertyBounds,
    accuracyStatus: {
      verifiedGroundTruth: false,
      disclaimer: ACCURACY_DISCLAIMER_TEXT,
    },
    metadata: data,
  };
}

/**
 * Normalizes single-room scan composite (outputs/c00a170fe1) into PropertyViewModel.
 * 
 * @param raw - Composite JSON containing room_polygon, measurements, openings, and damages.
 * @returns PropertyViewModel.
 */
export function normalizeSingleRoomScan(raw: unknown): PropertyViewModel {
  const data = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const captureId = typeof data.scan_id === 'string' ? data.scan_id : 'c00a170fe1';
  const tier: ReconstructionTier =
    data.tier === 'video' ? 'video' : data.tier === 'photo' ? 'photo' : 'lidar';

  const rawMeas = (data.measurements && typeof data.measurements === 'object'
    ? data.measurements
    : {}) as Record<string, unknown>;
  const rawPoly = (data.room_polygon && typeof data.room_polygon === 'object'
    ? data.room_polygon
    : {}) as Record<string, unknown>;

  const status = normalizeStatus(rawMeas.status || data.status, tier, captureId);

  // Extract polygon vertices
  const polygon: Point2D[] = [];
  const polyObj = rawPoly.polygon as Record<string, unknown> | undefined;
  const rawVerts = polyObj && Array.isArray(polyObj.vertices) ? polyObj.vertices : [];

  for (const v of rawVerts) {
    if (Array.isArray(v) && v.length >= 2) {
      polygon.push({ x: Number(v[0]) || 0, y: Number(v[1]) || 0 });
    }
  }

  // Extract walls
  const walls: WallViewModel[] = [];
  const rawWalls = Array.isArray(rawPoly.walls) ? rawPoly.walls : [];
  for (let wIdx = 0; wIdx < rawWalls.length; wIdx++) {
    walls.push(normalizeWall(rawWalls[wIdx], `wall_${wIdx + 1}`));
  }

  // Extract measurements
  const floorArea = normalizeValueWithConfidence(rawMeas.floor_area, 'm2');
  const perimeter = normalizeValueWithConfidence(rawMeas.perimeter, 'm');
  const ceilingHeight = normalizeValueWithConfidence(rawMeas.ceiling_height, 'm');
  const ceilingStatus =
    rawMeas.ceiling_status === 'observed'
      ? 'observed'
      : rawMeas.ceiling_status === 'indeterminate'
      ? 'indeterminate'
      : 'not_observed';

  // Extract openings
  const openings: OpeningViewModel[] = [];
  const rawOpenings = data.openings as Record<string, unknown> | undefined;
  if (rawOpenings && Array.isArray(rawOpenings.openings)) {
    for (const op of rawOpenings.openings) {
      openings.push(normalizeOpening(op));
    }
  }

  // Extract damages and scope
  const damages: DamageViewModel[] = [];
  const rawDamages = Array.isArray(data.damages) ? data.damages : [];
  const rawScope = Array.isArray(data.repair_scope) ? data.repair_scope : [];

  for (const dmg of rawDamages) {
    damages.push(normalizeDamage(dmg, rawScope));
  }

  const bounds = computeBoundingBox(polygon.length > 0 ? polygon : walls.map((w) => w.start));
  const center = computePolygonCentroid(polygon);

  const room: RoomViewModel = {
    id: 'room_01',
    name: 'Primary Room Scan',
    polygon,
    bounds,
    center,
    floorArea,
    perimeter,
    ceilingHeight,
    ceilingStatus,
    walls,
    openings,
    damages,
  };

  const statusReasons: string[] = [];
  if (Array.isArray(rawMeas.status_reasons)) {
    for (const r of rawMeas.status_reasons) {
      if (typeof r === 'string') statusReasons.push(r);
    }
  }

  return {
    id: `prop_${captureId}`,
    captureId,
    name: 'Single Room Scan with Defect Scope',
    tier,
    status,
    statusReasons,
    reconstructionMethod: 'arkit_lidar_unproject_ransac',
    totalFloorArea: floorArea,
    rooms: [room],
    bounds,
    accuracyStatus: {
      verifiedGroundTruth: false,
      disclaimer: ACCURACY_DISCLAIMER_TEXT,
    },
    metadata: data,
  };
}

/**
 * Normalizes failed or NOT_EVALUABLE property records (outputs/video_multi_room).
 * 
 * @param raw - Parsed raw JSON object.
 * @returns PropertyViewModel with zero rooms and failure reasons preserved.
 */
export function normalizeFailureProperty(raw: unknown): PropertyViewModel {
  const data = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const captureId = typeof data.capture_id === 'string' ? data.capture_id : 'failed_capture';
  const tier: ReconstructionTier =
    data.tier === 'video' ? 'video' : data.tier === 'photo' ? 'photo' : 'lidar';

  const failureReasons: string[] = [];
  if (Array.isArray(data.failure_reasons)) {
    for (const r of data.failure_reasons) {
      if (typeof r === 'string') failureReasons.push(r);
    }
  }

  return {
    id: `prop_${captureId}`,
    captureId,
    name: 'Video Multi-Room Sparse Drift Failure',
    tier,
    status: 'NOT_EVALUABLE',
    statusReasons: failureReasons,
    reconstructionMethod: 'rgb_video_colmap_sfm',
    totalFloorArea: null,
    rooms: [],
    bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0 },
    accuracyStatus: {
      verifiedGroundTruth: false,
      disclaimer: ACCURACY_DISCLAIMER_TEXT,
    },
    metadata: data,
  };
}

/**
 * Universal dispatcher selecting the correct adapter based on artifact shape.
 * 
 * @param raw - Any parsed backend fixture or API response.
 * @returns Fully normalized PropertyViewModel.
 */
export function adaptBackendProperty(raw: unknown): PropertyViewModel {
  if (!raw || typeof raw !== 'object') {
    return normalizeFailureProperty({ capture_id: 'empty', failure_reasons: ['empty_payload'] });
  }

  const d = raw as Record<string, unknown>;

  // Detect NOT_EVALUABLE state
  if (d.status === 'NOT_EVALUABLE' || (Array.isArray(d.rooms) && d.rooms.length === 0 && Array.isArray(d.failure_reasons))) {
    return normalizeFailureProperty(raw);
  }

  // Detect single room scan composite
  if (d.room_polygon || d.measurements) {
    return normalizeSingleRoomScan(raw);
  }

  // Multi-room property
  return normalizeMultiRoomProperty(raw);
}
