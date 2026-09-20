/**
 * @file exports.test.mjs
 * @purpose Unit tests for frontend export helpers, formats, URLs, and client fallback handling.
 * @stage Frontend Stage 4 — Exports + Final Product Polish.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { getCaptureExportUrl, getAcceptedFileTypes } from '../src/lib/api/captures.ts';

describe('Export URL Generation', () => {
  it('generates correct JSON export URL for dynamic capture ID', () => {
    const url = getCaptureExportUrl('cap_test_999', 'json');
    assert.match(url, /\/api\/captures\/cap_test_999\/exports\/json$/);
  });

  it('generates correct SVG export URL for dynamic capture ID', () => {
    const url = getCaptureExportUrl('cap_test_999', 'svg');
    assert.match(url, /\/api\/captures\/cap_test_999\/exports\/svg$/);
  });

  it('generates correct PDF export URL for dynamic capture ID', () => {
    const url = getCaptureExportUrl('cap_test_999', 'pdf');
    assert.match(url, /\/api\/captures\/cap_test_999\/exports\/pdf$/);
  });

  it('generates correct DXF export URL for dynamic capture ID', () => {
    const url = getCaptureExportUrl('cap_test_999', 'dxf');
    assert.match(url, /\/api\/captures\/cap_test_999\/exports\/dxf$/);
  });

  it('correctly encodes special characters in capture ID', () => {
    const url = getCaptureExportUrl('cap_test#01', 'json');
    assert.match(url, /\/api\/captures\/cap_test%2301\/exports\/json$/);
  });
});

describe('Tier Accepted File Types', () => {
  it('returns .zip for lidar', () => {
    assert.equal(getAcceptedFileTypes('lidar'), '.zip');
  });

  it('returns video formats for video', () => {
    const accepted = getAcceptedFileTypes('video');
    assert.ok(accepted.includes('.mp4'));
    assert.ok(accepted.includes('.mov'));
    assert.ok(accepted.includes('.zip'));
  });

  it('returns .zip for photo', () => {
    assert.equal(getAcceptedFileTypes('photo'), '.zip');
  });
});
