/**
 * @file bounds.ts
 * @purpose Geometric bounding box calculations for arbitrary 2D point sets, room polygons, and properties.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Arrays of Point2D objects or room polygon vertices in metric meters.
 * @outputs BoundingBox objects containing min/max coordinates and dimensions.
 * @dependencies ../domain/types
 * @assumptions Coordinates can be negative, non-origin centered, and in any order.
 * @failureModes Empty point array returns fallback origin box of zero dimensions.
 * @firstDebuggingPoints Check coordinate extents for negative numbers; ensure points are valid numbers.
 */

import { Point2D, BoundingBox } from '../domain/types';

/**
 * Calculates axis-aligned bounding box for an array of 2D points.
 * Handles negative coordinates, single points, and arbitrary scale.
 * 
 * @param points - Array of 2D points in meters.
 * @returns BoundingBox covering all provided points.
 * 
 * Units: meters.
 * Debugging clues: If width/height is zero, verify that at least 2 distinct points exist.
 */
export function computeBoundingBox(points: Point2D[]): BoundingBox {
  if (!points || points.length === 0) {
    return {
      minX: 0,
      maxX: 0,
      minY: 0,
      maxY: 0,
      width: 0,
      height: 0,
    };
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (let i = 0; i < points.length; i++) {
    const pt = points[i];
    if (typeof pt.x === 'number' && !isNaN(pt.x)) {
      if (pt.x < minX) minX = pt.x;
      if (pt.x > maxX) maxX = pt.x;
    }
    if (typeof pt.y === 'number' && !isNaN(pt.y)) {
      if (pt.y < minY) minY = pt.y;
      if (pt.y > maxY) maxY = pt.y;
    }
  }

  if (minX === Infinity) {
    return { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0 };
  }

  const width = Math.max(0, maxX - minX);
  const height = Math.max(0, maxY - minY);

  return {
    minX,
    maxX,
    minY,
    maxY,
    width,
    height,
  };
}

/**
 * Combines multiple bounding boxes into a single enclosing bounding box.
 * 
 * @param boxes - Array of bounding boxes to enclose.
 * @returns Combined enclosing bounding box.
 */
export function unionBoundingBoxes(boxes: BoundingBox[]): BoundingBox {
  const validBoxes = boxes.filter((b) => b.width > 0 || b.height > 0);
  if (validBoxes.length === 0) {
    return { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0 };
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const b of validBoxes) {
    if (b.minX < minX) minX = b.minX;
    if (b.maxX > maxX) maxX = b.maxX;
    if (b.minY < minY) minY = b.minY;
    if (b.maxY > maxY) maxY = b.maxY;
  }

  return {
    minX,
    maxX,
    minY,
    maxY,
    width: Math.max(0, maxX - minX),
    height: Math.max(0, maxY - minY),
  };
}
