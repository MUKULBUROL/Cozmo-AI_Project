/**
 * @file viewbox.ts
 * @purpose Pure deterministic SVG viewBox calculation and zoom/pan transformations.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs BoundingBox, padding factor, zoom multiplier, pan offsets.
 * @outputs SVG viewBox string (`minX minY width height`) and transform states.
 * @dependencies ../domain/types
 * @assumptions Aspect ratio is preserved by SVG's `preserveAspectRatio="xMidYMid meet"`. Zero or inverted geometry safely falls back to standard viewport.
 * @failureModes Zero-dimension bounds resulting in NaN viewBox values (safeguarded by minimum 1.0m box).
 * @firstDebuggingPoints Verify that zoom is > 0 and bounds has valid finite numbers.
 */

import { BoundingBox, Point2D } from '../domain/types';

/**
 * Options for computing the dynamic SVG viewBox.
 */
export interface ViewBoxOptions {
  paddingRatio?: number;
  zoom?: number;
  panOffset?: Point2D;
  minSpanMeters?: number;
}

/**
 * Computes an SVG viewBox string from bounding box geometry with configurable padding and zoom.
 * 
 * @param bounds - The bounding box of the floor plan in meters.
 * @param options - Configuration options for padding (default 0.08), zoom (default 1.0), and pan offset.
 * @returns Standard SVG viewBox string format: "minX minY width height"
 * 
 * Units: meters.
 * Debugging clues: Check that bounds.width and bounds.height are positive.
 */
export function computeViewBox(
  bounds: BoundingBox,
  options: ViewBoxOptions = {}
): string {
  const paddingRatio = options.paddingRatio ?? 0.08;
  const zoom = Math.max(0.1, Math.min(options.zoom ?? 1.0, 10.0));
  const panOffset = options.panOffset ?? { x: 0, y: 0 };
  const minSpan = options.minSpanMeters ?? 1.0;

  // Safeguard against zero/degenerate bounding boxes
  const effectiveWidth = Math.max(bounds.width, minSpan);
  const effectiveHeight = Math.max(bounds.height, minSpan);

  // Apply symmetric padding around geometric extent
  const padX = effectiveWidth * paddingRatio;
  const padY = effectiveHeight * paddingRatio;

  const paddedWidth = effectiveWidth + 2 * padX;
  const paddedHeight = effectiveHeight + 2 * padY;

  // Zoom is applied relative to geometric center
  const centerX = bounds.minX + bounds.width / 2;
  const centerY = bounds.minY + bounds.height / 2;

  const viewWidth = paddedWidth / zoom;
  const viewHeight = paddedHeight / zoom;

  const viewMinX = centerX - viewWidth / 2 + panOffset.x;
  const viewMinY = centerY - viewHeight / 2 + panOffset.y;

  // SVG Y-axis in browser points downward, but metric floor coordinates usually point upward.
  // We keep standard Cartesian coordinates; coordinate flipping is handled by transform or viewBox.
  return `${viewMinX.toFixed(4)} ${viewMinY.toFixed(4)} ${viewWidth.toFixed(4)} ${viewHeight.toFixed(4)}`;
}

/**
 * Calculates a point in the geometric center of a bounding box.
 * 
 * @param bounds - Geometric bounding box.
 * @returns Point2D at the center.
 */
export function getBoundsCenter(bounds: BoundingBox): Point2D {
  return {
    x: bounds.minX + bounds.width / 2,
    y: bounds.minY + bounds.height / 2,
  };
}
