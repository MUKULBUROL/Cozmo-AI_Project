/**
 * @file sync-fixtures.mjs
 * @purpose Deterministic synchronization of real backend JSON artifacts from outputs/ into frontend/src/data/generated/
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs JSON files in backend outputs/ directory (c7d28f72c6, c00a170fe1, fix_loop/stage11_video, video_multi_room, photo_property_01)
 * @outputs Static JSON fixtures in frontend/src/data/generated/ (manifest.json, lidar-c7d28f72c6.json, lidar-c00a170fe1.json, video-stage11.json, video-not-evaluable.json, photo-not-evaluable.json)
 * @dependencies node:fs, node:path, node:process
 * @assumptions Run from frontend/ directory or repository root. Never copies large binary/PLY/video files. Fails with exit code 1 if required artifacts are missing.
 * @failureModes Missing source outputs directory, corrupt JSON files, read/write permission errors.
 * @firstDebuggingPoints Check path resolution relative to process.cwd(), ensure backend stages have run and outputs/ exists.
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

/**
 * Resolves project root by searching upwards for outputs/ directory.
 * @param {string} startDir - Current working directory.
 * @returns {string} Absolute path to repo root containing outputs/
 * @throws {Error} If outputs directory cannot be found.
 */
function resolveProjectRoot(startDir) {
  const candidateDirs = [
    path.resolve(startDir, '..', 'CosmoAIProject'),
    path.resolve(startDir, '..'),
    path.resolve(startDir),
    path.resolve('/home/devcontainers/Projects/Active/CosmoAIProject'),
  ];

  for (const dir of candidateDirs) {
    const testPath = path.join(dir, 'outputs', 'c7d28f72c6', 'property', 'property.json');
    if (fs.existsSync(testPath)) {
      return dir;
    }
  }

  // Fallback to checking any outputs/
  let curr = path.resolve(startDir);
  for (let i = 0; i < 5; i++) {
    if (fs.existsSync(path.join(curr, 'outputs', 'c7d28f72c6'))) {
      return curr;
    }
    curr = path.dirname(curr);
  }
  throw new Error(`Unable to locate backend outputs containing c7d28f72c6 starting from ${startDir}`);
}

/**
 * Safely loads and parses a JSON file from disk.
 * @param {string} filePath - Path to JSON file.
 * @returns {unknown} Parsed JSON content.
 * @throws {Error} If file cannot be read or contains invalid JSON.
 */
function readJsonSafe(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Required JSON artifact missing: ${filePath}`);
  }
  const raw = fs.readFileSync(filePath, 'utf-8');
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`Malformed JSON in artifact ${filePath}: ${err.message}`);
  }
}

/**
 * Writes formatted JSON data to target path, ensuring directory exists.
 * @param {string} destPath - Destination file path.
 * @param {unknown} data - Data to serialize.
 */
function writeJsonSafe(destPath, data) {
  const dir = path.dirname(destPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(destPath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * Main execution function for fixture synchronization.
 * Synchronizes 5 distinct real-world scenarios:
 * 1. Multi-room LiDAR property (c7d28f72c6)
 * 2. Single-room LiDAR with measurements, openings, and Stage 9 damage (c00a170fe1)
 * 3. Video Stage 11 registration recovery (PROVISIONAL)
 * 4. Video multi-room failure (NOT_EVALUABLE)
 * 5. Photo property failure (NOT_EVALUABLE)
 */
function main() {
  console.log('[sync-fixtures] Starting deterministic fixture synchronization...');
  const repoRoot = resolveProjectRoot(process.cwd());
  console.log(`[sync-fixtures] Located project root: ${repoRoot}`);

  const frontendRoot = path.resolve(process.cwd(), process.cwd().endsWith('frontend') ? '.' : 'frontend');
  const destDir = path.join(frontendRoot, 'src', 'data', 'generated');

  console.log(`[sync-fixtures] Destination directory: ${destDir}`);

  // Scenario 1: Multi-room LiDAR property (c7d28f72c6)
  const lidarMultiPath = path.join(repoRoot, 'outputs', 'c7d28f72c6', 'property', 'property.json');
  const lidarMultiData = readJsonSafe(lidarMultiPath);

  // Scenario 2: Single-room LiDAR with measurements, openings, damage (c00a170fe1)
  const lidarSingleDir = path.join(repoRoot, 'outputs', 'c00a170fe1');
  const c00aPolygon = readJsonSafe(path.join(lidarSingleDir, 'floorplan_geometry', 'room_polygon.json'));
  const c00aMeasurements = readJsonSafe(path.join(lidarSingleDir, 'measurements', 'measurements.json'));
  const c00aOpenings = readJsonSafe(path.join(lidarSingleDir, 'openings', 'openings.json'));
  const c00aDamages = readJsonSafe(path.join(lidarSingleDir, 'damage', 'damages.json'));
  const c00aDamageSummary = readJsonSafe(path.join(lidarSingleDir, 'damage', 'damage_summary.json'));
  const c00aRepairScope = readJsonSafe(path.join(lidarSingleDir, 'damage', 'repair_scope.json'));
  const c00aStats = readJsonSafe(path.join(lidarSingleDir, 'reconstruction_stats.json'));

  const lidarSingleComposite = {
    scan_id: 'c00a170fe1',
    tier: 'lidar',
    status: c00aMeasurements.status || 'provisional',
    room_polygon: c00aPolygon,
    measurements: c00aMeasurements,
    openings: c00aOpenings,
    damages: c00aDamages,
    damage_summary: c00aDamageSummary,
    repair_scope: c00aRepairScope,
    stats: c00aStats,
  };

  // Scenario 3: Video Stage 11 Multi-room Recovery (PROVISIONAL)
  const videoStage11Dir = path.join(repoRoot, 'outputs', 'fix_loop', 'stage11_video');
  const videoStage11Prop = readJsonSafe(path.join(videoStage11Dir, 'after', 'property.json'));
  const videoStage11Comp = readJsonSafe(path.join(videoStage11Dir, 'comparison.json'));
  const videoStage11Stats = readJsonSafe(path.join(videoStage11Dir, 'after', 'reconstruction_stats.json'));

  const videoStage11Composite = {
    ...videoStage11Prop,
    tier: 'video',
    status: 'PROVISIONAL', // Strictly preserved as PROVISIONAL as required
    comparison: videoStage11Comp,
    reconstruction_stats: videoStage11Stats,
  };

  // Scenario 4: Video Multi-Room Failure State (NOT_EVALUABLE)
  const videoFailurePath = path.join(repoRoot, 'outputs', 'video_multi_room', 'video', 'property', 'property.json');
  const videoFailureData = readJsonSafe(videoFailurePath);

  // Scenario 5: Photo Property Failure State (NOT_EVALUABLE)
  const photoFailurePath = path.join(repoRoot, 'outputs', 'photo_property_01', 'photo', 'property', 'property.json');
  const photoFailureData = readJsonSafe(photoFailurePath);

  // Write individual fixture files
  writeJsonSafe(path.join(destDir, 'lidar-property-c7d28f72c6.json'), lidarMultiData);
  writeJsonSafe(path.join(destDir, 'lidar-room-c00a170fe1.json'), lidarSingleComposite);
  writeJsonSafe(path.join(destDir, 'video-stage11-provisional.json'), videoStage11Composite);
  writeJsonSafe(path.join(destDir, 'video-not-evaluable.json'), videoFailureData);
  writeJsonSafe(path.join(destDir, 'photo-not-evaluable.json'), photoFailureData);

  // Write manifest index
  const manifest = {
    syncedAt: new Date().toISOString(),
    fixtures: [
      {
        id: 'c7d28f72c6',
        name: 'Residential Property (Multi-Room)',
        tier: 'lidar',
        status: 'COMPLETE',
        roomCount: lidarMultiData.rooms ? lidarMultiData.rooms.length : 0,
        totalAreaM2: lidarMultiData.total_floor_area?.value ?? null,
        fileName: 'lidar-property-c7d28f72c6.json',
        description: 'ARKIt pose-graph optimized LiDAR reconstruction with 4 rooms, shared walls, and verified bounds.',
      },
      {
        id: 'c00a170fe1',
        name: 'Single Room Scan with Defect Scope',
        tier: 'lidar',
        status: 'PROVISIONAL',
        roomCount: 1,
        totalAreaM2: c00aMeasurements.floor_area?.value ?? 7.554,
        fileName: 'lidar-room-c00a170fe1.json',
        description: 'Single-room LiDAR scan with polygon geometry, doorway openings, water stain damage, and Stage 9 repair scope.',
      },
      {
        id: 'stage11-video',
        name: 'Stage 11 Video Multi-Room Recovery',
        tier: 'video',
        status: 'PROVISIONAL',
        roomCount: videoStage11Prop.rooms ? videoStage11Prop.rooms.length : 1,
        totalAreaM2: videoStage11Prop.total_floor_area?.value ?? 18.97,
        fileName: 'video-stage11-provisional.json',
        description: 'RGB video SfM reconstruction with metric depth scale. Improved 4/40 -> 31/40 registered views. Strictly PROVISIONAL.',
      },
      {
        id: 'video-multi-room-failure',
        name: 'Video Multi-Room Sparse Drift Failure',
        tier: 'video',
        status: 'NOT_EVALUABLE',
        roomCount: 0,
        totalAreaM2: null,
        fileName: 'video-not-evaluable.json',
        description: 'Sparse video track with insufficient keyframe registration (<30% threshold). Documents explicit failure reasons.',
      },
      {
        id: 'photo-property-failure',
        name: 'Uncalibrated Photo Property Failure',
        tier: 'photo',
        status: 'NOT_EVALUABLE',
        roomCount: 0,
        totalAreaM2: null,
        fileName: 'photo-not-evaluable.json',
        description: 'Photo tier property reconstruction failure showing unaligned room components.',
      },
    ],
  };

  writeJsonSafe(path.join(destDir, 'manifest.json'), manifest);
  console.log('[sync-fixtures] Successfully synced 5 real backend fixtures + manifest.json');
}

try {
  main();
} catch (error) {
  console.error('[sync-fixtures] FATAL ERROR:', error.message);
  process.exit(1);
}
