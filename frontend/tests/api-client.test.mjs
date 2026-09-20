/**
 * @file api-client.test.mjs
 * @purpose Tests for the API client, capture lifecycle, and error handling.
 * @stage Frontend Stage 3 — Live FastAPI Integration.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { CaptureCreatedSchema, CaptureStatusSchema, isTerminalStatus } from '../src/lib/api/schemas.ts';

describe('CaptureCreatedSchema validates API response', () => {
  it('accepts valid creation response', () => {
    const data = { id: 'cap_a1b2c3d4', tier: 'lidar', status: 'QUEUED' };
    const result = CaptureCreatedSchema.parse(data);
    assert.equal(result.id, 'cap_a1b2c3d4');
    assert.equal(result.tier, 'lidar');
  });

  it('rejects response missing id', () => {
    assert.throws(() => {
      CaptureCreatedSchema.parse({ tier: 'video', status: 'QUEUED' });
    });
  });

  it('rejects invalid tier', () => {
    assert.throws(() => {
      CaptureCreatedSchema.parse({ id: 'x', tier: 'invalid', status: 'QUEUED' });
    });
  });
});

describe('CaptureStatusSchema validates polling response', () => {
  it('accepts COMPLETE status', () => {
    const data = {
      id: 'cap_test123',
      tier: 'lidar',
      status: 'COMPLETE',
      created_at: '2026-01-01T00:00:00Z',
      progress_stage: 'Complete',
      error: null,
    };
    const result = CaptureStatusSchema.parse(data);
    assert.equal(result.status, 'COMPLETE');
  });

  it('accepts PROVISIONAL status', () => {
    const data = {
      id: 'cap_video01',
      tier: 'video',
      status: 'PROVISIONAL',
      created_at: '2026-01-01T00:00:00Z',
      progress_stage: null,
      error: null,
    };
    const result = CaptureStatusSchema.parse(data);
    assert.equal(result.status, 'PROVISIONAL');
  });

  it('accepts NOT_EVALUABLE status', () => {
    const data = {
      id: 'cap_fail01',
      tier: 'photo',
      status: 'NOT_EVALUABLE',
      created_at: '2026-01-01T00:00:00Z',
      error: 'Insufficient overlap',
    };
    const result = CaptureStatusSchema.parse(data);
    assert.equal(result.status, 'NOT_EVALUABLE');
  });

  it('accepts FAILED status with error', () => {
    const data = {
      id: 'cap_err01',
      tier: 'lidar',
      status: 'FAILED',
      created_at: '2026-01-01T00:00:00Z',
      error: 'Missing odometry.csv',
    };
    const result = CaptureStatusSchema.parse(data);
    assert.equal(result.status, 'FAILED');
    assert.equal(result.error, 'Missing odometry.csv');
  });

  it('accepts PROCESSING status with progress stage', () => {
    const data = {
      id: 'cap_proc01',
      tier: 'lidar',
      status: 'PROCESSING',
      created_at: '2026-01-01T00:00:00Z',
      progress_stage: 'Reconstructing geometry',
    };
    const result = CaptureStatusSchema.parse(data);
    assert.equal(result.progress_stage, 'Reconstructing geometry');
  });

  it('rejects malformed status response', () => {
    assert.throws(() => {
      CaptureStatusSchema.parse({ id: 'x', status: 'UNKNOWN_JUNK' });
    });
  });
});

describe('Terminal status detection', () => {
  it('identifies COMPLETE as terminal', () => {
    assert.ok(isTerminalStatus('COMPLETE'));
  });

  it('identifies PROVISIONAL as terminal', () => {
    assert.ok(isTerminalStatus('PROVISIONAL'));
  });

  it('identifies NOT_EVALUABLE as terminal', () => {
    assert.ok(isTerminalStatus('NOT_EVALUABLE'));
  });

  it('identifies FAILED as terminal', () => {
    assert.ok(isTerminalStatus('FAILED'));
  });

  it('identifies PROCESSING as non-terminal', () => {
    assert.ok(!isTerminalStatus('PROCESSING'));
  });

  it('identifies QUEUED as non-terminal', () => {
    assert.ok(!isTerminalStatus('QUEUED'));
  });

  it('identifies UPLOADING as non-terminal', () => {
    assert.ok(!isTerminalStatus('UPLOADING'));
  });
});

describe('No hardcoded fixture IDs in API schemas', () => {
  it('schemas do not reference c7d28f72c6', () => {
    const schemaStr = JSON.stringify(CaptureStatusSchema);
    assert.ok(!schemaStr.includes('c7d28f72c6'));
  });

  it('schemas do not reference c00a170fe1', () => {
    const schemaStr = JSON.stringify(CaptureStatusSchema);
    assert.ok(!schemaStr.includes('c00a170fe1'));
  });
});

describe('adaptBackendProperty handles all result states honestly without fixture fallback', () => {
  it('handles COMPLETE state for dynamic capture ID', async () => {
    const { adaptBackendProperty } = await import('../src/domain/adapters.ts');
    const dynamicId = 'cap_dyn_999';
    const payload = {
      property_id: dynamicId,
      capture_id: dynamicId,
      tier: 'lidar',
      status: 'COMPLETE',
      rooms: [
        {
          room_id: 'room_01',
          name: 'Main Area',
          walls: [],
          floor_area: { value: 30.5, unit: 'm2' },
        },
      ],
      total_floor_area: { value: 30.5, unit: 'm2' },
    };

    const vm = adaptBackendProperty(payload);
    assert.equal(vm.captureId, dynamicId);
    assert.equal(vm.status, 'COMPLETE');
    assert.equal(vm.rooms.length, 1);
    assert.notEqual(vm.captureId, 'c7d28f72c6');
  });

  it('handles PROVISIONAL state for dynamic video capture ID', async () => {
    const { adaptBackendProperty } = await import('../src/domain/adapters.ts');
    const dynamicId = 'cap_video_xyz';
    const payload = {
      property_id: dynamicId,
      capture_id: dynamicId,
      tier: 'video',
      status: 'PROVISIONAL',
      rooms: [
        {
          room_id: 'room_01',
          name: 'Video Room',
          walls: [],
          floor_area: { value: 15.2, unit: 'm2' },
        },
      ],
    };

    const vm = adaptBackendProperty(payload);
    assert.equal(vm.captureId, dynamicId);
    assert.equal(vm.status, 'PROVISIONAL');
    assert.equal(vm.tier, 'video');
  });

  it('handles NOT_EVALUABLE state with failure reasons', async () => {
    const { adaptBackendProperty } = await import('../src/domain/adapters.ts');
    const dynamicId = 'cap_noteval_001';
    const payload = {
      property_id: dynamicId,
      capture_id: dynamicId,
      tier: 'video',
      status: 'NOT_EVALUABLE',
      rooms: [],
      failure_reasons: ['Feature matching failed: visual overlap < 20%'],
    };

    const vm = adaptBackendProperty(payload);
    assert.equal(vm.captureId, dynamicId);
    assert.equal(vm.status, 'NOT_EVALUABLE');
    assert.equal(vm.rooms.length, 0);
    assert.ok(vm.statusReasons.includes('Feature matching failed: visual overlap < 20%'));
  });

  it('handles FAILED state payload gracefully without crashing', async () => {
    const { adaptBackendProperty } = await import('../src/domain/adapters.ts');
    const dynamicId = 'cap_failed_002';
    const payload = {
      property_id: dynamicId,
      capture_id: dynamicId,
      status: 'FAILED',
      failure_reasons: ['Process terminated with exit code 1'],
    };

    const vm = adaptBackendProperty(payload);
    assert.equal(vm.captureId, dynamicId);
    assert.ok(vm.status === 'FAILED' || vm.status === 'NOT_EVALUABLE');
  });

  it('handles null or malformed response safely', async () => {
    const { adaptBackendProperty } = await import('../src/domain/adapters.ts');
    const vm = adaptBackendProperty(null);
    assert.equal(vm.status, 'NOT_EVALUABLE');
    assert.equal(vm.rooms.length, 0);
  });
});

