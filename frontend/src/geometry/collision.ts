/**
 * @file collision.ts
 * @purpose Deterministic label collision detection and priority-based dimension placement.
 * @stage Frontend Stage 3 — Floor Plan UX Improvements.
 * @inputs Wall dimension labels, room name labels, zoom level, selected room/wall context.
 * @outputs Visibility decisions for each label: SHOW, HIDE, or OFFSET.
 * @dependencies ../domain/types.
 * @assumptions Labels are rectangular axis-aligned bounding boxes in SVG coordinate space (meters). Font size is proportional to zoom.
 * @failureModes Degenerate (zero-area) labels treated as invisible. Extremely dense plans may hide most labels.
 * @firstDebuggingPoints Check label bounds computation; verify zoom-scaled font dimensions; inspect priority ordering.
 */

import { Point2D } from '../domain/types';

/**
 * Axis-aligned bounding rectangle for a label in SVG coordinate space.
 * Units: meters (matching floor plan coordinate space).
 */
export interface LabelRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Priority level for label rendering order.
 * Lower numeric value = higher display priority.
 */
export enum LabelPriority {
  /** Currently selected wall dimension — always shown. */
  SELECTED_WALL = 0,
  /** Wall dimensions within the selected room. */
  SELECTED_ROOM = 1,
  /** Room name labels. */
  ROOM_NAME = 2,
  /** Major room dimensions (floor area text). */
  MAJOR_DIMENSION = 3,
  /** All remaining wall dimension labels. */
  OTHER_DIMENSION = 4,
}

/**
 * Candidate label awaiting collision resolution.
 */
export interface LabelCandidate {
  /** Unique label identifier (e.g. wall_id or room_id). */
  id: string;
  /** Preferred label position in SVG space. */
  position: Point2D;
  /** Estimated label dimensions in SVG coordinate units. */
  bounds: LabelRect;
  /** Display priority (lower = more important). */
  priority: LabelPriority;
  /** Label text content. */
  text: string;
  /** Wall/room association for alternate offset computation. */
  wallStart?: Point2D;
  wallEnd?: Point2D;
}

/**
 * Resolved placement decision for a label.
 */
export interface LabelPlacement {
  /** The original candidate. */
  candidate: LabelCandidate;
  /** Whether the label should be rendered. */
  visible: boolean;
  /** Final position (may differ from candidate if offset was applied). */
  position: Point2D;
}

/**
 * Estimate label bounding rect from position, text length, and font size.
 *
 * @param position - Center point of the label.
 * @param textLength - Number of characters in the label text.
 * @param fontSizeMeters - Font size in SVG coordinate meters.
 * @returns Estimated axis-aligned LabelRect.
 *
 * Assumptions: Average character width ≈ 0.55 × font size.
 * Debugging: If labels overlap despite this check, increase the width multiplier.
 */
export function estimateLabelBounds(
  position: Point2D,
  textLength: number,
  fontSizeMeters: number,
): LabelRect {
  const charWidth = fontSizeMeters * 0.55;
  const width = charWidth * textLength + fontSizeMeters * 0.6; // padding
  const height = fontSizeMeters * 1.4;

  return {
    x: position.x - width / 2,
    y: position.y - height / 2,
    width,
    height,
  };
}

/**
 * Check whether two axis-aligned label rectangles overlap.
 *
 * @param a - First label bounds.
 * @param b - Second label bounds.
 * @param margin - Additional margin around each rect (meters).
 * @returns True if the rectangles overlap.
 *
 * Debugging: Visualise both rects if false positives occur.
 */
export function checkCollision(
  a: LabelRect,
  b: LabelRect,
  margin = 0.02,
): boolean {
  return !(
    a.x + a.width + margin <= b.x ||
    b.x + b.width + margin <= a.x ||
    a.y + a.height + margin <= b.y ||
    b.y + b.height + margin <= a.y
  );
}

/**
 * Compute an alternate offset position for a wall dimension label.
 *
 * @param start - Wall start point.
 * @param end - Wall end point.
 * @param originalOffset - Original perpendicular offset (meters).
 * @param attemptIndex - Retry attempt (1, 2, 3...).
 * @returns Alternate label position moved further from the wall.
 *
 * Assumptions: Each attempt moves 0.15m further perpendicular to the wall.
 */
export function computeAlternateOffset(
  start: Point2D,
  end: Point2D,
  originalOffset: number,
  attemptIndex: number,
): Point2D {
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const len = Math.hypot(dx, dy);

  if (len < 1e-4) {
    return { x: midX, y: midY };
  }

  const nx = -dy / len;
  const ny = dx / len;
  const offset = originalOffset + attemptIndex * 0.15;

  return {
    x: midX + nx * offset,
    y: midY + ny * offset,
  };
}

/**
 * Determine which wall dimension labels to show at the current zoom level.
 *
 * @param zoom - Current zoom factor (1.0 = fit-to-view).
 * @param totalLabels - Total number of candidate labels.
 * @returns Maximum number of labels to display.
 *
 * Assumptions: At low zoom, fewer labels are readable.
 * At zoom ≥ 2.0, all labels may be shown if they don't collide.
 */
export function getMaxLabelsForZoom(zoom: number, totalLabels: number): number {
  if (zoom >= 3.0) return totalLabels;
  if (zoom >= 2.0) return Math.min(totalLabels, Math.max(20, totalLabels));
  if (zoom >= 1.0) return Math.min(totalLabels, 15);
  if (zoom >= 0.5) return Math.min(totalLabels, 8);
  return Math.min(totalLabels, 4);
}

/**
 * Resolve label placements using priority-based collision avoidance.
 *
 * Algorithm:
 *   1. Sort candidates by priority (lower = placed first).
 *   2. For each candidate, check collision against already-placed labels.
 *   3. If no collision → place at original position.
 *   4. If collision → try up to 3 alternate offsets.
 *   5. If all offsets collide → hide the label (it remains in Inspector).
 *
 * @param candidates - Array of label candidates to resolve.
 * @param maxLabels - Maximum visible labels (zoom-dependent).
 * @returns Array of LabelPlacement decisions.
 *
 * Debugging: Check that candidates are sorted correctly by priority.
 */
export function resolveCollisions(
  candidates: LabelCandidate[],
  maxLabels: number = Infinity,
): LabelPlacement[] {
  // Sort by priority (most important first)
  const sorted = [...candidates].sort((a, b) => a.priority - b.priority);
  const placedBounds: LabelRect[] = [];
  const results: LabelPlacement[] = [];
  let visibleCount = 0;

  for (const candidate of sorted) {
    // Zoom limit reached
    if (visibleCount >= maxLabels) {
      results.push({
        candidate,
        visible: false,
        position: candidate.position,
      });
      continue;
    }

    // Check collision at original position
    const hasCollision = placedBounds.some((placed) =>
      checkCollision(candidate.bounds, placed)
    );

    if (!hasCollision) {
      placedBounds.push(candidate.bounds);
      results.push({
        candidate,
        visible: true,
        position: candidate.position,
      });
      visibleCount++;
      continue;
    }

    // Try alternate offsets (up to 3 attempts)
    if (candidate.wallStart && candidate.wallEnd) {
      let placed = false;
      for (let attempt = 1; attempt <= 3; attempt++) {
        const altPos = computeAlternateOffset(
          candidate.wallStart,
          candidate.wallEnd,
          0.15,
          attempt,
        );
        const altBounds = estimateLabelBounds(
          altPos,
          candidate.text.length,
          candidate.bounds.height / 1.4, // reverse-engineer font size
        );

        const altCollides = placedBounds.some((p) =>
          checkCollision(altBounds, p)
        );

        if (!altCollides) {
          placedBounds.push(altBounds);
          results.push({
            candidate,
            visible: true,
            position: altPos,
          });
          visibleCount++;
          placed = true;
          break;
        }
      }

      if (!placed) {
        results.push({
          candidate,
          visible: false,
          position: candidate.position,
        });
      }
    } else {
      // No wall geometry → can't offset → hide
      results.push({
        candidate,
        visible: false,
        position: candidate.position,
      });
    }
  }

  return results;
}

/**
 * Compute a readable text rotation angle for a wall dimension label.
 * Normalises to avoid upside-down text.
 *
 * @param start - Wall start point.
 * @param end - Wall end point.
 * @returns Rotation angle in degrees [−90, 90].
 *
 * Assumptions: Text should never be rotated more than 90° from horizontal.
 */
export function computeLabelRotation(start: Point2D, end: Point2D): number {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  let angle = Math.atan2(dy, dx) * (180 / Math.PI);

  // Normalize to readable orientation (never upside-down)
  if (angle > 90) angle -= 180;
  if (angle < -90) angle += 180;

  return angle;
}
