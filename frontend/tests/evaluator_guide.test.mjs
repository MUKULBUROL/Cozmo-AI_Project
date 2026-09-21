import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

describe('Evaluator Demonstration Experience Validation', () => {
  const demoPagePath = path.resolve(process.cwd(), 'src/app/demo/page.tsx');
  const guidePagePath = path.resolve(process.cwd(), 'src/app/evaluator-guide/page.tsx');
  const docPath = path.resolve(process.cwd(), '../docs/EVALUATOR_DEMONSTRATION.md');
  const readmePath = path.resolve(process.cwd(), '../README.md');

  test('Demo page file exists and is populated', () => {
    assert.ok(fs.existsSync(demoPagePath), 'src/app/demo/page.tsx must exist');
    const content = fs.readFileSync(demoPagePath, 'utf8');
    assert.ok(content.includes('Evaluate COZMO'), 'Must contain header title');
    assert.ok(content.includes('Backend-Only Demonstration'), 'Must contain backend section');
    assert.ok(content.includes('Frontend Demonstration'), 'Must contain frontend section');
    assert.ok(content.includes('reconstruct_lidar.py'), 'Must contain lidar CLI command');
    assert.ok(content.includes('reconstruct_video.py'), 'Must contain video CLI command');
    assert.ok(content.includes('reconstruct_photos.py'), 'Must contain photo CLI command');
    assert.ok(content.includes('single_room.zip'), 'Must contain sample data references');
    assert.ok(content.includes('COMPLETE'), 'Must explain COMPLETE status');
    assert.ok(content.includes('NOT_EVALUABLE'), 'Must explain NOT_EVALUABLE status');
    assert.ok(content.includes('CommandBlock'), 'Must implement copyable command block');
  });

  test('Evaluator guide route alias exists and imports demo page', () => {
    assert.ok(fs.existsSync(guidePagePath), 'src/app/evaluator-guide/page.tsx must exist');
    const content = fs.readFileSync(guidePagePath, 'utf8');
    assert.ok(content.includes('../demo/page'), 'Must re-export demo page');
  });

  test('Documentation mirror exists and matches CLI commands', () => {
    assert.ok(fs.existsSync(docPath), 'docs/EVALUATOR_DEMONSTRATION.md must exist');
    const content = fs.readFileSync(docPath, 'utf8');
    assert.ok(content.includes('COZMO — Evaluator Demonstration Guide'), 'Must have correct title');
    assert.ok(content.includes('scripts/reconstruct_lidar.py'), 'Must have lidar command');
    assert.ok(content.includes('scripts/reconstruct_property.py'), 'Must have property command');
    assert.ok(content.includes('scripts/reconstruct_video.py'), 'Must have video command');
    assert.ok(content.includes('scripts/reconstruct_photos.py'), 'Must have photo command');
    assert.ok(content.includes('outputs/<id>/property/property.json'), 'Must have outputs documentation');
  });

  test('README includes Evaluator Demonstration references', () => {
    assert.ok(fs.existsSync(readmePath), 'README.md must exist');
    const content = fs.readFileSync(readmePath, 'utf8');
    assert.ok(content.includes('Evaluator Demonstration'), 'Must have Evaluator Demonstration section');
    assert.ok(content.includes('/demo'), 'Must link to /demo route');
    assert.ok(content.includes('docs/EVALUATOR_DEMONSTRATION.md'), 'Must link to markdown guide');
  });
});
