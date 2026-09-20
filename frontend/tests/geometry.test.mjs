/**
 * @file geometry.test.mjs
 * @purpose Unit tests for bounding box calculations and SVG viewBox generation.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Synthetic point sets (positive, negative, collinear, degenerate).
 * @outputs Test assertions executed via Node.js test runner.
 * @dependencies node:test, node:assert/strict
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { computeBoundingBox, unionBoundingBoxes } from '../src/geometry/bounds.ts';
import { computeViewBox } from '../src/geometry/viewbox.ts';
import { computePolygonCentroid, pointsToSvgPath } from '../src/geometry/polygon.ts';

test('computeBoundingBox correctly handles positive and negative coordinates', () => {
  const points = [
    { x: -2.5, y: -1.0 },
    { x: 3.5, y: 4.0 },
    { x: 0.0, y: 2.0 },
  ];
  const box = computeBoundingBox(points);

  assert.equal(box.minX, -2.5);
  assert.equal(box.maxX, 3.5);
  assert.equal(box.minY, -1.0);
  assert.equal(box.maxY, 4.0);
  assert.equal(box.width, 6.0);
  assert.equal(box.height, 5.0);
});

test('computeBoundingBox handles empty array safely', () => {
  const box = computeBoundingBox([]);
  assert.equal(box.width, 0);
  assert.equal(box.height, 0);
});

test('unionBoundingBoxes combines multiple disjoint boxes', () => {
  const box1 = { minX: 0, maxX: 2, minY: 0, maxY: 3, width: 2, height: 3 };
  const box2 = { minX: 4, maxX: 7, minY: -1, maxY: 1, width: 3, height: 2 };

  const combined = unionBoundingBoxes([box1, box2]);
  assert.equal(combined.minX, 0);
  assert.equal(combined.maxX, 7);
  assert.equal(combined.minY, -1);
  assert.equal(combined.maxY, 3);
  assert.equal(combined.width, 7);
  assert.equal(combined.height, 4);
});

test('computeViewBox generates valid 4-number SVG string with padding', () => {
  const box = { minX: 0, maxX: 10, minY: 0, maxY: 10, width: 10, height: 10 };
  const vb = computeViewBox(box, { paddingRatio: 0.1, zoom: 1.0 });

  const parts = vb.split(' ').map(Number);
  assert.equal(parts.length, 4);
  assert.ok(parts[0] < 0, 'minX should include negative padding');
  assert.ok(parts[1] < 0, 'minY should include negative padding');
  assert.ok(parts[2] > 10, 'width should include symmetric padding');
  assert.ok(parts[3] > 10, 'height should include symmetric padding');
});

test('computePolygonCentroid calculates center of rectangle', () => {
  const rect = [
    { x: 0, y: 0 },
    { x: 4, y: 0 },
    { x: 4, y: 2 },
    { x: 0, y: 2 },
  ];
  const center = computePolygonCentroid(rect);
  assert.ok(Math.abs(center.x - 2.0) < 1e-4);
  assert.ok(Math.abs(center.y - 1.0) < 1e-4);
});

test('pointsToSvgPath generates standard SVG path format', () => {
  const pts = [
    { x: 1, y: 2 },
    { x: 3, y: 4 },
  ];
  const path = pointsToSvgPath(pts, true);
  assert.equal(path, 'M 1.0000 2.0000 L 3.0000 4.0000 Z');
});
