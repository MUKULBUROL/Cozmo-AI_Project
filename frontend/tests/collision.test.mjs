/**
 * @file collision.test.mjs
 * @purpose Tests for label collision detection, priority-based placement, and zoom-dependent visibility.
 * @stage Frontend Stage 3 — Floor Plan UX Improvements.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  checkCollision,
  estimateLabelBounds,
  resolveCollisions,
  getMaxLabelsForZoom,
  computeAlternateOffset,
  computeLabelRotation,
  LabelPriority,
} from '../src/geometry/collision.ts';

describe('checkCollision detects overlapping rectangles', () => {
  it('detects full overlap', () => {
    const a = { x: 0, y: 0, width: 1, height: 1 };
    const b = { x: 0.5, y: 0.5, width: 1, height: 1 };
    assert.ok(checkCollision(a, b, 0));
  });

  it('detects no overlap for separated rects', () => {
    const a = { x: 0, y: 0, width: 1, height: 1 };
    const b = { x: 2, y: 2, width: 1, height: 1 };
    assert.ok(!checkCollision(a, b, 0));
  });

  it('respects margin parameter', () => {
    const a = { x: 0, y: 0, width: 1, height: 1 };
    const b = { x: 1.01, y: 0, width: 1, height: 1 };
    assert.ok(!checkCollision(a, b, 0));    // No overlap without margin
    assert.ok(checkCollision(a, b, 0.02));  // Overlap with margin
  });

  it('handles adjacent rects (sharing edge)', () => {
    const a = { x: 0, y: 0, width: 1, height: 1 };
    const b = { x: 1, y: 0, width: 1, height: 1 };
    // Adjacent but not overlapping (touching edge)
    assert.ok(!checkCollision(a, b, 0));
  });
});

describe('estimateLabelBounds calculates reasonable bounds', () => {
  it('produces positive width and height', () => {
    const bounds = estimateLabelBounds({ x: 5, y: 3 }, 6, 0.13);
    assert.ok(bounds.width > 0);
    assert.ok(bounds.height > 0);
  });

  it('centers bounds on the position', () => {
    const pos = { x: 5, y: 3 };
    const bounds = estimateLabelBounds(pos, 6, 0.13);
    const centerX = bounds.x + bounds.width / 2;
    const centerY = bounds.y + bounds.height / 2;
    assert.ok(Math.abs(centerX - 5) < 0.01);
    assert.ok(Math.abs(centerY - 3) < 0.01);
  });

  it('longer text produces wider bounds', () => {
    const short = estimateLabelBounds({ x: 0, y: 0 }, 3, 0.13);
    const long = estimateLabelBounds({ x: 0, y: 0 }, 10, 0.13);
    assert.ok(long.width > short.width);
  });
});

describe('resolveCollisions respects priority ordering', () => {
  it('shows high-priority labels over low-priority on collision', () => {
    const pos = { x: 5, y: 5 };
    const candidates = [
      {
        id: 'low',
        position: pos,
        bounds: estimateLabelBounds(pos, 5, 0.2),
        priority: LabelPriority.OTHER_DIMENSION,
        text: 'low',
      },
      {
        id: 'high',
        position: pos,
        bounds: estimateLabelBounds(pos, 5, 0.2),
        priority: LabelPriority.ROOM_NAME,
        text: 'high',
      },
    ];

    const results = resolveCollisions(candidates);
    const highResult = results.find(r => r.candidate.id === 'high');
    const lowResult = results.find(r => r.candidate.id === 'low');

    assert.ok(highResult?.visible, 'High priority label should be visible');
    assert.ok(!lowResult?.visible, 'Low priority label should be hidden on collision');
  });

  it('shows all labels when no collision', () => {
    const candidates = [
      {
        id: 'a',
        position: { x: 0, y: 0 },
        bounds: estimateLabelBounds({ x: 0, y: 0 }, 3, 0.1),
        priority: LabelPriority.ROOM_NAME,
        text: 'A',
      },
      {
        id: 'b',
        position: { x: 10, y: 10 },
        bounds: estimateLabelBounds({ x: 10, y: 10 }, 3, 0.1),
        priority: LabelPriority.OTHER_DIMENSION,
        text: 'B',
      },
    ];

    const results = resolveCollisions(candidates);
    assert.ok(results.every(r => r.visible));
  });
});

describe('getMaxLabelsForZoom returns reasonable limits', () => {
  it('allows all labels at high zoom', () => {
    assert.equal(getMaxLabelsForZoom(3.0, 50), 50);
  });

  it('limits labels at low zoom', () => {
    const max = getMaxLabelsForZoom(0.3, 50);
    assert.ok(max <= 8, `Expected <= 8, got ${max}`);
  });

  it('returns at least 4 at any zoom', () => {
    assert.ok(getMaxLabelsForZoom(0.1, 100) >= 4);
  });
});

describe('computeAlternateOffset produces offset positions', () => {
  it('returns midpoint at attempt 0 equivalent', () => {
    const pos = computeAlternateOffset(
      { x: 0, y: 0 }, { x: 4, y: 0 }, 0.15, 0
    );
    assert.ok(Math.abs(pos.x - 2) < 0.01, `x should be ~2, got ${pos.x}`);
  });

  it('moves further from wall on higher attempts', () => {
    const pos1 = computeAlternateOffset(
      { x: 0, y: 0 }, { x: 4, y: 0 }, 0.15, 1
    );
    const pos2 = computeAlternateOffset(
      { x: 0, y: 0 }, { x: 4, y: 0 }, 0.15, 2
    );
    // Perpendicular offset should increase
    assert.ok(Math.abs(pos2.y) > Math.abs(pos1.y));
  });
});

describe('computeLabelRotation normalises to readable angles', () => {
  it('horizontal wall produces 0° rotation', () => {
    const angle = computeLabelRotation({ x: 0, y: 0 }, { x: 4, y: 0 });
    assert.ok(Math.abs(angle) < 0.1);
  });

  it('vertical wall produces ±90° rotation', () => {
    const angle = computeLabelRotation({ x: 0, y: 0 }, { x: 0, y: 4 });
    assert.ok(Math.abs(angle) === 90 || Math.abs(angle - 90) < 0.1);
  });

  it('never produces upside-down text (angle stays in [-90, 90])', () => {
    // Test several wall orientations
    const angles = [
      computeLabelRotation({ x: 0, y: 0 }, { x: -4, y: -2 }),
      computeLabelRotation({ x: 0, y: 0 }, { x: -4, y: 2 }),
      computeLabelRotation({ x: 0, y: 0 }, { x: 4, y: -2 }),
    ];
    for (const a of angles) {
      assert.ok(a >= -90 && a <= 90, `Angle ${a} outside [-90, 90]`);
    }
  });
});
