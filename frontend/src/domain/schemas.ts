/**
 * @file schemas.ts
 * @purpose Runtime validation schemas for external backend JSON artifacts using Zod.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Raw parsed JSON artifacts from fixture files or API responses.
 * @outputs Validated runtime data structures or clear parsing diagnostics.
 * @dependencies zod
 * @assumptions Backend schemas adhere to FRONTEND_DATA_CONTRACT.md. Optional fields may be missing or null.
 * @failureModes Schema mismatch throws ZodError with detailed path breakdown.
 * @firstDebuggingPoints Check raw JSON field names against schema definitions below.
 */

import { z } from 'zod';

/**
 * Value with confidence interval and measurement method metadata.
 */
export const RawValueWithIntervalSchema = z.object({
  value: z.number(),
  unit: z.string().optional().default('m'),
  lower_bound: z.number().optional(),
  upper_bound: z.number().optional(),
  interval: z.tuple([z.number(), z.number()]).optional(),
  confidence: z.number().optional(),
  method: z.string().optional(),
});

/**
 * 2D point object ({ x, y }) or coordinate pair ([x, y]).
 */
export const RawPointSchema = z.union([
  z.object({ x: z.number(), y: z.number() }),
  z.tuple([z.number(), z.number()]).transform(([x, y]) => ({ x, y })),
]);

/**
 * Raw wall segment representation from multi-room property or room polygon.
 */
export const RawWallSchema = z.object({
  wall_id: z.string(),
  start: RawPointSchema,
  end: RawPointSchema,
  length: z.union([RawValueWithIntervalSchema, z.number().transform((val) => ({ value: val, unit: 'm' }))]).optional(),
  thickness: RawValueWithIntervalSchema.nullable().optional(),
  height: RawValueWithIntervalSchema.nullable().optional(),
  length_m: z.number().optional(),
});

/**
 * Raw opening representation (doorway / window).
 */
export const RawOpeningSchema = z.object({
  id: z.string(),
  type: z.string().optional().default('doorway'),
  wall_id: z.string().optional().default(''),
  status: z.string().optional().default('provisional'),
  width: z.union([RawValueWithIntervalSchema, z.number().transform((val) => ({ value: val, unit: 'm' }))]).optional(),
  calibrated: z.boolean().optional().default(false),
  detector_confidence: z.number().optional(),
  left_jamb_3d: z.array(z.number()).optional(),
  right_jamb_3d: z.array(z.number()).optional(),
});

/**
 * Raw concealed defect flag.
 */
export const RawConcealedFlagSchema = z.object({
  rule_id: z.string(),
  suspected_issue: z.string(),
  requires_inspection: z.boolean().optional().default(false),
  inspection_recommendation: z.string().optional().default(''),
});

/**
 * Raw repair scope item.
 */
export const RawScopeItemSchema = z.object({
  line_item_id: z.string(),
  damage_id: z.string(),
  action: z.string(),
  target_surface: z.string(),
  quantity: z.number(),
  unit: z.string(),
  basis: z.string().optional().default(''),
  confidence: z.number().optional().default(1.0),
  inspection_required: z.boolean().optional().default(false),
});

/**
 * Raw damage detection representation.
 */
export const RawDamageSchema = z.object({
  damage_id: z.string(),
  damage_class: z.string(),
  class_confidence: z.number().optional().default(1.0),
  host_surface_id: z.string().nullable().optional(),
  host_surface_type: z.string().optional().default('wall'),
  metric_area: RawValueWithIntervalSchema.nullable().optional(),
  metric_length: RawValueWithIntervalSchema.nullable().optional(),
  status: z.string().optional().default('ACCEPTED'),
  concealed_flags: z.array(RawConcealedFlagSchema).optional().default([]),
  scope_line_items: z.array(RawScopeItemSchema).optional().default([]),
});

/**
 * Multi-room property JSON schema (outputs/c7d28f72c6/property/property.json).
 */
export const RawMultiRoomPropertySchema = z.object({
  property_id: z.string().optional(),
  capture_id: z.string().optional(),
  tier: z.enum(['lidar', 'video', 'photo']).optional().default('lidar'),
  status: z.string().optional(),
  rooms: z.array(
    z.object({
      room_id: z.string(),
      name: z.string().optional(),
      floor_area: RawValueWithIntervalSchema.nullable().optional(),
      perimeter: RawValueWithIntervalSchema.nullable().optional(),
      ceiling_height: RawValueWithIntervalSchema.nullable().optional(),
      walls: z.array(RawWallSchema).optional().default([]),
      openings: z.array(RawOpeningSchema).optional().default([]),
      damage_regions: z.array(RawDamageSchema).optional().default([]),
    })
  ).optional().default([]),
  connections: z.array(z.any()).optional().default([]),
  total_floor_area: RawValueWithIntervalSchema.nullable().optional(),
  reconstruction_method: z.string().nullable().optional(),
  failure_reasons: z.array(z.string()).optional(),
  note: z.string().optional(),
});

export type RawMultiRoomProperty = z.infer<typeof RawMultiRoomPropertySchema>;
export type RawDamage = z.infer<typeof RawDamageSchema>;
export type RawScopeItem = z.infer<typeof RawScopeItemSchema>;
