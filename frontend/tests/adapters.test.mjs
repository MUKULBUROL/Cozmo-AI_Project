/**
 * @file adapters.test.mjs
 * @purpose Unit tests for backend artifact normalization and integrity rules.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Real fixture files in src/data/generated/
 * @outputs Test assertions ensuring zero invented values, strict PROVISIONAL video state, and safe error states.
 * @dependencies node:test, node:assert/strict, node:fs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  adaptBackendProperty,
  normalizeStatus,
  formatDamageLabel,
  ACCURACY_DISCLAIMER_TEXT,
} from '../src/domain/adapters.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = path.join(__dirname, '..', 'src', 'data', 'generated');

test('Multi-room LiDAR property (c7d28f72c6) adapts with 4 rooms and valid bounds', () => {
  const raw = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, 'lidar-property-c7d28f72c6.json'), 'utf-8'));
  const property = adaptBackendProperty(raw);

  assert.equal(property.tier, 'lidar');
  assert.equal(property.status, 'COMPLETE');
  assert.equal(property.rooms.length, 4);
  assert.ok(property.bounds.width > 0);
  assert.ok(property.bounds.height > 0);
  assert.equal(property.accuracyStatus.verifiedGroundTruth, false);
  assert.equal(property.accuracyStatus.disclaimer, ACCURACY_DISCLAIMER_TEXT);
});

test('Single-room LiDAR (c00a170fe1) ceiling height is strictly null/not_observed (never 2.45m)', () => {
  const raw = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, 'lidar-room-c00a170fe1.json'), 'utf-8'));
  const property = adaptBackendProperty(raw);

  assert.equal(property.rooms.length, 1);
  const room = property.rooms[0];
  assert.equal(room.ceilingHeight, null, 'Ceiling height must be null when backend reports not_observed');
  assert.equal(room.ceilingStatus, 'not_observed');
  assert.ok(room.damages.length >= 2, 'Stage 9 damages must be attached to room');
  assert.ok(room.openings.length >= 1, 'Openings must be attached to room');
});

test('Video Stage 11 result strictly preserves PROVISIONAL status', () => {
  const raw = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, 'video-stage11-provisional.json'), 'utf-8'));
  const property = adaptBackendProperty(raw);

  assert.equal(property.tier, 'video');
  assert.equal(property.status, 'PROVISIONAL', 'Video Stage 11 must NEVER be marked COMPLETE');
});

test('Video failure state adapts to NOT_EVALUABLE with failure reasons', () => {
  const raw = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, 'video-not-evaluable.json'), 'utf-8'));
  const property = adaptBackendProperty(raw);

  assert.equal(property.tier, 'video');
  assert.equal(property.status, 'NOT_EVALUABLE');
  assert.equal(property.rooms.length, 0);
  assert.ok(property.statusReasons.length > 0);
});

test('normalizeStatus preserves truthfulness across all tiers', () => {
  assert.equal(normalizeStatus('complete', 'video'), 'PROVISIONAL', 'Video can never be complete in Stage 2');
  assert.equal(normalizeStatus('NOT_EVALUABLE', 'video'), 'NOT_EVALUABLE');
  assert.equal(normalizeStatus('COMPLETE', 'lidar', 'c7d28f72c6'), 'COMPLETE');
  assert.equal(normalizeStatus('provisional', 'lidar', 'c00a170fe1'), 'PROVISIONAL');
});

test('formatDamageLabel maps canonical defect names to human-readable Title Case labels', () => {
  assert.equal(formatDamageLabel('crack_structural'), 'Structural Crack');
  assert.equal(formatDamageLabel('water_stain'), 'Water Stain');
  assert.equal(formatDamageLabel('surface_crack'), 'Surface Crack');
  assert.equal(formatDamageLabel('mold_like_discoloration'), 'Mold Discoloration');
  assert.equal(formatDamageLabel('hole_or_missing_material'), 'Hole / Missing Material');
  assert.equal(formatDamageLabel('other_visible_damage'), 'Visible Defect');
  assert.equal(formatDamageLabel('impact'), 'Hole / Missing Material');
  assert.equal(formatDamageLabel('custom_damage_type'), 'Custom Damage Type');
});
