/**
 * @file types.ts
 * @purpose Core domain ViewModel interfaces and types for the Cozmo Spatial Pro frontend.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs None (type definitions)
 * @outputs Strongly typed ViewModels consumed by React canvas, inspectors, and navigation components.
 * @dependencies None
 * @assumptions Coordinates are in metric meters (m), areas in square meters (m²). All missing values are represented honestly as null without synthetic fallbacks.
 * @failureModes Type mismatches during adapter conversion.
 * @firstDebuggingPoints Check adapter conversions in adapters.ts against backend raw artifact schemas in FRONTEND_DATA_CONTRACT.md.
 */

/**
 * 2D point in metric floor plan coordinate space (meters).
 */
export interface Point2D {
  x: number;
  y: number;
}

/**
 * 2D axis-aligned bounding box for viewport calculation.
 */
export interface BoundingBox {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  height: number;
}

/**
 * Measurement value accompanied by confidence bounds and estimation metadata.
 */
export interface ValueWithConfidence {
  value: number;
  unit: string;
  lowerBound?: number;
  upperBound?: number;
  interval?: [number, number];
  confidence?: number;
  method?: string;
}

/**
 * Reconstruction sensor tier.
 */
export type ReconstructionTier = 'lidar' | 'video' | 'photo';

/**
 * Official backend reconstruction status.
 */
export type ReconstructionStatus = 'COMPLETE' | 'PROVISIONAL' | 'NOT_EVALUABLE' | 'FAILED';

/**
 * Normalized wall segment ViewModel for floor plan rendering and inspector details.
 */
export interface WallViewModel {
  id: string;
  start: Point2D;
  end: Point2D;
  length: ValueWithConfidence;
  thickness: ValueWithConfidence | null;
  height: ValueWithConfidence | null;
  labelPoint: Point2D;
}

/**
 * Doorway or opening ViewModel for floor plan rendering.
 */
export interface OpeningViewModel {
  id: string;
  type: 'doorway' | 'window' | 'pass_through';
  wallId: string;
  width: ValueWithConfidence;
  status: string;
  calibrated: boolean;
  leftJamb?: Point2D;
  rightJamb?: Point2D;
}

/**
 * Concealed defect risk flag from Stage 9 damage engine.
 */
export interface ConcealedRiskFlag {
  ruleId: string;
  suspectedIssue: string;
  requiresInspection: boolean;
  recommendation: string;
}

/**
 * Remediation scope line item ViewModel.
 */
export interface ScopeItemViewModel {
  id: string;
  damageId: string;
  action: string;
  targetSurface: string;
  quantity: number;
  unit: string;
  basis: string;
  confidence: number;
  inspectionRequired: boolean;
}

/**
 * Surface damage defect ViewModel.
 */
export interface DamageViewModel {
  id: string;
  damageClass: string;
  confidence: number;
  hostSurfaceId: string;
  hostSurfaceType: string;
  metricArea: ValueWithConfidence | null;
  metricLength: ValueWithConfidence | null;
  status: string;
  concealedFlags: ConcealedRiskFlag[];
  scopeItems: ScopeItemViewModel[];
}

/**
 * Room ViewModel representing a reconstructed room boundary and its internal components.
 */
export interface RoomViewModel {
  id: string;
  name: string;
  polygon: Point2D[];
  bounds: BoundingBox;
  center: Point2D;
  floorArea: ValueWithConfidence | null;
  perimeter: ValueWithConfidence | null;
  ceilingHeight: ValueWithConfidence | null;
  ceilingStatus: 'observed' | 'not_observed' | 'indeterminate';
  walls: WallViewModel[];
  openings: OpeningViewModel[];
  damages: DamageViewModel[];
}

/**
 * Complete Property ViewModel backing the entire Spatial Pro workspace.
 */
export interface PropertyViewModel {
  id: string;
  captureId: string;
  name: string;
  tier: ReconstructionTier;
  status: ReconstructionStatus;
  statusReasons: string[];
  reconstructionMethod: string | null;
  totalFloorArea: ValueWithConfidence | null;
  rooms: RoomViewModel[];
  bounds: BoundingBox;
  accuracyStatus: {
    verifiedGroundTruth: boolean;
    disclaimer: string;
  };
  metadata: Record<string, unknown>;
}
