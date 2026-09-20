/**
 * @file fixture-loader.ts
 * @purpose Loads and manages real backend JSON fixtures for Frontend Stage 2.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs Pre-synced JSON fixtures in src/data/generated/
 * @outputs Strongly-typed PropertyViewModel objects and fixture scenario manifests.
 * @dependencies ../domain/types, ../domain/adapters
 * @assumptions Fixtures originate from real backend execution outputs and are synced via `npm run fixtures:sync`.
 * @failureModes Unknown fixture ID returns null; malformed JSON caught with fallback error model.
 * @firstDebuggingPoints Verify that `src/data/generated/manifest.json` exists; run `npm run fixtures:sync` if missing.
 */

import { PropertyViewModel } from '../domain/types';
import { adaptBackendProperty } from '../domain/adapters';

import manifestData from './generated/manifest.json';
import lidarC7Data from './generated/lidar-property-c7d28f72c6.json';
import lidarC00Data from './generated/lidar-room-c00a170fe1.json';
import videoStage11Data from './generated/video-stage11-provisional.json';
import videoNotEvalData from './generated/video-not-evaluable.json';
import photoNotEvalData from './generated/photo-not-evaluable.json';

export interface FixtureSummary {
  id: string;
  name: string;
  tier: 'lidar' | 'video' | 'photo';
  status: 'COMPLETE' | 'PROVISIONAL' | 'NOT_EVALUABLE' | 'FAILED';
  roomCount: number;
  totalAreaM2: number | null;
  fileName: string;
  description: string;
}

/**
 * Static registry of all approved Stage 2 fixtures.
 */
const FIXTURE_MAP: Record<string, unknown> = {
  c7d28f72c6: lidarC7Data,
  prop_c7d28f72c6: lidarC7Data,
  c00a170fe1: lidarC00Data,
  prop_c00a170fe1: lidarC00Data,
  'stage11-video': videoStage11Data,
  prop_video_multi_room: videoStage11Data,
  'video-multi-room-failure': videoNotEvalData,
  video_multi_room: videoNotEvalData,
  'photo-property-failure': photoNotEvalData,
  photo_property_01: photoNotEvalData,
};

/**
 * Returns list of all available fixture summaries for the landing workspace.
 * 
 * @returns Array of FixtureSummary objects.
 */
export function getAllFixtureSummaries(): FixtureSummary[] {
  return manifestData.fixtures as FixtureSummary[];
}

/**
 * Loads a property by its ID, adapting it to PropertyViewModel.
 * 
 * @param id - Capture or property ID (e.g., 'c7d28f72c6', 'c00a170fe1', 'stage11-video').
 * @returns Normalized PropertyViewModel or null if ID is not recognized.
 */
export function getPropertyById(id: string): PropertyViewModel | null {
  const raw = FIXTURE_MAP[id];
  if (!raw) return null;

  try {
    const model = adaptBackendProperty(raw);
    // Explicit title overrides for clarity in workspace
    if (id === 'c7d28f72c6' || id === 'prop_c7d28f72c6') {
      model.name = 'Residential Property (Multi-Room)';
    } else if (id === 'c00a170fe1' || id === 'prop_c00a170fe1') {
      model.name = 'Single Room Scan with Defect Scope';
    } else if (id === 'stage11-video' || id === 'prop_video_multi_room') {
      model.name = 'Stage 11 Video Multi-Room Recovery';
      model.status = 'PROVISIONAL'; // Strict verification
    } else if (id === 'video-multi-room-failure' || id === 'video_multi_room') {
      model.name = 'Video Multi-Room Sparse Drift Failure';
      model.status = 'NOT_EVALUABLE';
    } else if (id === 'photo-property-failure' || id === 'photo_property_01') {
      model.name = 'Uncalibrated Photo Property Failure';
      model.status = 'NOT_EVALUABLE';
    }
    return model;
  } catch (err) {
    console.error(`Failed to adapt fixture ${id}:`, err);
    return null;
  }
}
