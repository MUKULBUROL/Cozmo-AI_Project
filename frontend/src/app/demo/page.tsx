/**
 * @file page.tsx
 * @purpose Evaluator Demonstration Experience for COZMO spatial reconstruction platform.
 * @stage Frontend Final Polish — Evaluator Demonstration Layer.
 * @inputs None (standalone interactive evaluator guide).
 * @outputs Accessible demonstration guide matching Spatial Pro aesthetic with copyable commands,
 *          plain-language explanations, status matrices, and responsive desktop/tablet/mobile layout.
 * @dependencies react, next/link, ../../components/ui/StatusBadge, ../../components/ui/TierBadge
 */

'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { StatusBadge } from '../../components/ui/StatusBadge';

function CommandBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback if clipboard API unavailable
    }
  };

  return (
    <div style={{ position: 'relative', margin: '8px 0 14px 0' }}>
      <pre className="command-box">
        <code>{code}</code>
      </pre>
      <button
        type="button"
        onClick={handleCopy}
        className="copy-btn"
        aria-label="Copy command to clipboard"
      >
        {copied ? (
          <>
            <span style={{ color: 'var(--success-text)', fontWeight: 700 }}>✓</span>
            <span style={{ color: 'var(--success-text)' }}>Copied</span>
          </>
        ) : (
          <>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <span>Copy</span>
          </>
        )}
      </button>
    </div>
  );
}

export default function EvaluatorDemoPage() {
  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--background)', display: 'flex', flexDirection: 'column' }}>
      {/* Top Header */}
      <header
        style={{
          height: 'var(--topbar-height)',
          backgroundColor: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          position: 'sticky',
          top: 0,
          zIndex: 30,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none' }}>
            <div
              style={{
                width: '24px',
                height: '24px',
                backgroundColor: 'var(--text-primary)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--surface)',
                fontWeight: 700,
                fontSize: '13px',
              }}
            >
              C
            </div>
            <span style={{ fontWeight: 700, fontSize: '14px', letterSpacing: '0.04em', color: 'var(--text-primary)' }}>
              COZMO
            </span>
          </Link>
          <span style={{ color: 'var(--border-strong)', fontSize: '13px' }}>/</span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Evaluator Demonstration Guide
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link
            href="/"
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary)',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              backgroundColor: 'var(--surface)',
            }}
          >
            ← Back to Workspaces
          </Link>
          <Link
            href="/new"
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--text-on-primary)',
              backgroundColor: 'var(--primary)',
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              textDecoration: 'none',
            }}
          >
            + New Capture
          </Link>
        </div>
      </header>

      {/* Main Content Layout */}
      <main
        style={{
          maxWidth: '1120px',
          width: '100%',
          margin: '32px auto',
          padding: '0 20px',
        }}
      >
        <div className="demo-layout">
          {/* Main Body Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>

            {/* SECTION 1 — QUICK OVERVIEW */}
            <section id="overview" className="property-card" style={{ padding: '28px' }}>
              <div style={{ marginBottom: '16px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--primary)',
                    display: 'inline-block',
                    marginBottom: '4px',
                  }}
                >
                  Evaluator Guide
                </span>
                <h1
                  style={{
                    fontSize: '26px',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    letterSpacing: '-0.02em',
                    lineHeight: 1.25,
                    margin: '0 0 10px 0',
                  }}
                >
                  Evaluate COZMO
                </h1>
                <p style={{ fontSize: '15px', color: 'var(--text-secondary)', lineHeight: 1.55, margin: 0 }}>
                  COZMO reconstructs measurable floor plans from LiDAR captures, handheld video, or room photos.
                </p>
              </div>

              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
                You can evaluate the system in two ways:
              </div>

              <div className="demo-grid-2">
                <div
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '16px',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    Backend Only
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
                    Run reconstruction directly from the command line and inspect raw artifacts.
                  </p>
                </div>

                <div
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '16px',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    Frontend
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
                    Upload a capture through the COZMO web interface and inspect interactive results.
                  </p>
                </div>
              </div>
            </section>

            {/* SECTION 2 — CHOOSE EVALUATION METHOD */}
            <section id="choose-method" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '16px' }}>
                Choose Evaluation Method
              </h2>

              <div className="demo-grid-2">
                <div
                  style={{
                    backgroundColor: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                      <span className="mono" style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)' }}>
                        CLI
                      </span>
                      <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                        BACKEND ONLY
                      </h3>
                    </div>

                    <div style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      Best for:
                    </div>
                    <ul style={{ paddingLeft: '18px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: '0 0 16px 0' }}>
                      <li>Reproducibility verification</li>
                      <li>Direct pipeline testing</li>
                      <li>Inspecting raw artifacts</li>
                      <li>Automated benchmarking</li>
                    </ul>
                  </div>

                  <a
                    href="#backend-demo"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      padding: '8px 16px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'var(--surface-subtle)',
                      border: '1px solid var(--border-strong)',
                      color: 'var(--text-primary)',
                      fontSize: '13px',
                      fontWeight: 600,
                      textDecoration: 'none',
                    }}
                  >
                    View Backend Demo ↓
                  </a>
                </div>

                <div
                  style={{
                    backgroundColor: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                      <span className="mono" style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--primary-subtle)', color: 'var(--primary)', border: '1px solid var(--primary-border)' }}>
                        WEB UI
                      </span>
                      <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                        FRONTEND
                      </h3>
                    </div>

                    <div style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      Best for:
                    </div>
                    <ul style={{ paddingLeft: '18px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: '0 0 16px 0' }}>
                      <li>Full evaluator experience</li>
                      <li>Upload → Process → Inspect → Export</li>
                      <li>Interactive 2D floor plans & room clicks</li>
                      <li>Homeowner-facing result flow</li>
                    </ul>
                  </div>

                  <a
                    href="#frontend-demo"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      padding: '8px 16px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'var(--primary)',
                      color: 'var(--text-on-primary)',
                      fontSize: '13px',
                      fontWeight: 600,
                      textDecoration: 'none',
                    }}
                  >
                    View Frontend Demo ↓
                  </a>
                </div>
              </div>
            </section>

            {/* SECTION 3 — BACKEND-ONLY DEMONSTRATION */}
            <section id="backend-demo" className="property-card" style={{ padding: '28px' }}>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Backend-Only Demonstration
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                  This route runs COZMO directly from the command line and writes reconstruction artifacts to the <code>outputs</code> directory.
                </p>
              </div>

              {/* Step 1 Setup */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 1
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Environment Setup
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  Clone the repository, create a virtual environment, and install dependencies:
                </p>
                <CommandBlock
                  code={`git clone https://github.com/MUKULBUROL/Cozmo-AI_Project.git
cd Cozmo-AI_Project

python3 -m venv .venv
source .venv/bin/activate

pip install -e .`}
                />
              </div>

              {/* Step 2 Available Sample Data */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 2
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Available Sample Data
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                  The assessor-provided samples are stored in <code>sample data/</code>:
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '12px' }}>
                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                    <div className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      sample data/single_room.zip
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Single-room sensor capture containing RGB video, LiDAR depth, confidence maps, camera poses, intrinsics, and IMU.
                    </div>
                  </div>

                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                    <div className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      sample data/single_scan_floor_only.zip
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Larger floor-focused sensor capture.
                    </div>
                  </div>

                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                    <div className="mono" style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      sample data/single_scan_with_ceiling.zip
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Multi-room / whole-property capture with ceiling observations.
                    </div>
                  </div>
                </div>

                <div className="callout-box warning">
                  <strong>Important Notice:</strong> These files contain metric sensor inputs (depth streams and odometry poses), not independent laser/tape ground truth.
                </div>
              </div>

              {/* Step 3 LiDAR Demo */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 3
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    LiDAR Reconstruction Command
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Run metric reconstruction on the floor-only sample:
                </p>
                <CommandBlock
                  code={`python3 scripts/reconstruct_lidar.py --scan 1a8384c3f6 --archive "sample data/single_scan_floor_only.zip" --voxel-size 0.02`}
                />

                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '10px 0 6px 0' }}>
                  Or run the multi-room whole-property pipeline with loop closure and drift correction:
                </p>
                <CommandBlock
                  code={`python3 scripts/reconstruct_property.py --scan c7d28f72c6 --archive "sample data/single_scan_with_ceiling.zip" --headless`}
                />

                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '10px' }}>
                  <strong>Expected outputs generated:</strong>
                  <ul style={{ paddingLeft: '18px', marginTop: '4px', lineHeight: 1.6 }}>
                    <li>Point cloud (<code>outputs/1a8384c3f6/pointcloud.ply</code>)</li>
                    <li>Trajectory and structural planes (<code>outputs/1a8384c3f6/structures.json</code>)</li>
                    <li>Wall geometry and room/property model (<code>outputs/c7d28f72c6/property/property.json</code>)</li>
                    <li>Measurements & openings (<code>outputs/1a8384c3f6/measurements.json</code>)</li>
                    <li>Diagnostic SVGs (<code>outputs/c7d28f72c6/property/drift_ablation.svg</code>)</li>
                  </ul>
                </div>
              </div>

              {/* Step 4 Video Demo */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 4
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Video Reconstruction Command
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Run monocular walkthrough reconstruction using RGB video only:
                </p>
                <CommandBlock
                  code={`python3 scripts/reconstruct_video.py --archive "sample data/single_room.zip" --scan c00a170fe1 --capture-id video_rec_01 --max-keyframes 30`}
                />

                <div className="callout-box" style={{ marginTop: '10px' }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                    Pipeline Stages (RGB Only):
                  </div>
                  <div style={{ fontSize: '12.5px', lineHeight: 1.6 }}>
                    RGB frames → Feature matching & camera pose reconstruction → Metric depth estimation → Metric point cloud → Shared geometry engine → Floor plan.
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Notice: Video reconstruction operates strictly on RGB imagery and does not utilize LiDAR depth streams or odometry poses.
                  </div>
                </div>
              </div>

              {/* Step 5 Photo Demo */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 5
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Photo Reconstruction Command
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Run reconstruction from a folder of overlapping room still photos:
                </p>
                <CommandBlock
                  code={`python3 scripts/reconstruct_photos.py --input "data/photo_dev/sample_room" --capture-id photo_rec_01`}
                />

                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px', lineHeight: 1.5 }}>
                  <strong>Expected input structure:</strong> 2–8 still images per room (e.g. <code>photos/room_01/image1.jpg</code>, <code>image2.jpg</code>, <code>image3.jpg</code>).
                </div>
                <div className="callout-box" style={{ marginTop: '8px' }}>
                  <strong>Data Integrity Note:</strong> Real photo inputs are clearly distinguished from development photo sets extracted from supplied video. Development sets extracted from video are explicitly labeled.
                </div>
              </div>

              {/* Step 6 Backend Outputs */}
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 6
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Backend Output Artifacts
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                  Reconstruction artifacts are written directly to structured workspace directories:
                </p>

                <div className="table-responsive">
                  <table className="demo-table">
                    <thead>
                      <tr>
                        <th>Output Category</th>
                        <th>Path Pattern</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>Point Cloud</strong></td>
                        <td className="mono" style={{ fontSize: '12px' }}>outputs/&lt;id&gt;/pointcloud.ply</td>
                        <td>Downsampled 3D metric point cloud</td>
                      </tr>
                      <tr>
                        <td><strong>Structural Planes</strong></td>
                        <td className="mono" style={{ fontSize: '12px' }}>outputs/&lt;id&gt;/structures.json</td>
                        <td>RANSAC floor, ceiling, and wall planes</td>
                      </tr>
                      <tr>
                        <td><strong>Measurements</strong></td>
                        <td className="mono" style={{ fontSize: '12px' }}>outputs/&lt;id&gt;/measurements.json</td>
                        <td>Wall lengths and 95% confidence intervals</td>
                      </tr>
                      <tr>
                        <td><strong>Property JSON</strong></td>
                        <td className="mono" style={{ fontSize: '12px' }}>outputs/&lt;id&gt;/property/property.json</td>
                        <td>Complete schema with rooms, walls, openings</td>
                      </tr>
                      <tr>
                        <td><strong>Diagnostic SVG</strong></td>
                        <td className="mono" style={{ fontSize: '12px' }}>outputs/&lt;id&gt;/property/drift_ablation.svg</td>
                        <td>Trajectory comparison and pose graph loop residuals</td>
                      </tr>
                      <tr>
                        <td><strong>Benchmark Artifacts</strong></td>
                        <td className="mono" style={{ fontSize: '12px' }}>benchmark/results/metrics.json</td>
                        <td>Computed accuracy metrics and challenge gate summaries</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            {/* SECTION 4 — FRONTEND DEMONSTRATION */}
            <section id="frontend-demo" className="property-card" style={{ padding: '28px' }}>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Frontend Demonstration
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                  This route evaluates the complete COZMO product workflow.
                </p>
              </div>

              {/* Step 1 Start Backend */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 1
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Start Backend API Server
                  </h3>
                </div>
                <CommandBlock
                  code={`python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`}
                />
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', gap: '20px', marginTop: '4px' }}>
                  <span>Health Check: <code className="mono">http://localhost:8000/api/health</code></span>
                  <span>API Docs: <code className="mono">http://localhost:8000/docs</code></span>
                </div>
              </div>

              {/* Step 2 Start Frontend */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 2
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Start Frontend Workspace
                  </h3>
                </div>
                <CommandBlock
                  code={`cd frontend
npm ci
npm run dev`}
                />
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  Open browser at: <code className="mono">http://localhost:3000</code>
                </div>
              </div>

              {/* Step 3 Upload */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 3
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Upload a Capture
                  </h3>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  Follow the UI workflow:
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '8px 0', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Home</span>
                    <span>→</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>New Capture</span>
                    <span>→</span>
                    <span>Choose <strong>LiDAR</strong>, <strong>Video</strong>, or <strong>Photos</strong></span>
                    <span>→</span>
                    <span>Choose File</span>
                    <span>→</span>
                    <span style={{ fontWeight: 600, color: 'var(--primary)' }}>Process Capture</span>
                  </div>
                  <p style={{ margin: '4px 0 0 0' }}>
                    For LiDAR demonstration, recommend uploading <code>single_room.zip</code> or <code>single_scan_with_ceiling.zip</code>.
                  </p>
                </div>
              </div>

              {/* Step 4 Processing */}
              <div style={{ marginBottom: '22px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 4
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Processing Lifecycle
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                  During processing the UI shows progress through clear states: <strong>Queued</strong> → <strong>Processing</strong> → <strong>Complete</strong> (or honest limitation/failure states if input is insufficient).
                </p>
              </div>

              {/* Step 5 Result Page */}
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--surface-subtle)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                    Step 5
                  </span>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Inspect Reconstructed Property
                  </h3>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                  On the workspace page (<code>/property/&lt;id&gt;</code>), the evaluator can inspect:
                </p>
                <div className="demo-grid-3" style={{ marginBottom: '12px' }}>
                  <div style={{ padding: '10px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '13px' }}>
                    <strong>Floor Plan</strong>: 2D vector drawing with pan/zoom
                  </div>
                  <div style={{ padding: '10px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '13px' }}>
                    <strong>Rooms & Walls</strong>: Interactive polygons & metric dimensions
                  </div>
                  <div style={{ padding: '10px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '13px' }}>
                    <strong>Ceiling Height</strong>: Estimated vertical span (if observed)
                  </div>
                  <div style={{ padding: '10px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '13px' }}>
                    <strong>Openings</strong>: Doorways and windows detected
                  </div>
                  <div style={{ padding: '10px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '13px' }}>
                    <strong>Damage & Scope</strong>: Classified defects and suggested repairs
                  </div>
                  <div style={{ padding: '10px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '13px' }}>
                    <strong>Exports</strong>: JSON, SVG, PDF, and DXF downloads
                  </div>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  <em>Tip: Click any room in the floor plan or left sidebar to inspect its detailed wall schedule and dimension intervals.</em>
                </div>
              </div>
            </section>

            {/* SECTION 5 — SAMPLE DATA TABLE */}
            <section id="sample-data" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Sample Data Table
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                Assessor-provided sample archives available in the repository:
              </p>

              <div className="table-responsive">
                <table className="demo-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Type</th>
                      <th>Best Demo Use</th>
                      <th>Expected Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="mono" style={{ fontWeight: 600, fontSize: '12.5px' }}>single_room.zip</td>
                      <td>LiDAR sensor archive</td>
                      <td>Quick end-to-end demo</td>
                      <td style={{ color: 'var(--text-secondary)' }}>Ceiling may be unobserved depending on capture geometry</td>
                    </tr>
                    <tr>
                      <td className="mono" style={{ fontWeight: 600, fontSize: '12.5px' }}>single_scan_floor_only.zip</td>
                      <td>LiDAR sensor archive</td>
                      <td>Floor-focused reconstruction / property demonstration</td>
                      <td style={{ color: 'var(--text-secondary)' }}>Ceiling expected unavailable</td>
                    </tr>
                    <tr>
                      <td className="mono" style={{ fontWeight: 600, fontSize: '12.5px' }}>single_scan_with_ceiling.zip</td>
                      <td>LiDAR multi-room sensor archive</td>
                      <td>Multi-room, drift, ceiling demonstration</td>
                      <td style={{ color: 'var(--text-secondary)' }}>Best structural/multi-room example</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="callout-box" style={{ marginTop: '14px' }}>
                <strong>Ground-Truth Note:</strong> The sample archives contain metric depth sensor readings and odometry trajectories; they do not contain certified laser disto or tape ground-truth measurements.
              </div>
            </section>

            {/* SECTION 6 — UNDERSTANDING THE RESULT */}
            <section id="results" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Understanding the Results
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                What each architectural result entity represents:
              </p>

              <div className="demo-grid-2">
                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    ROOMS
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Distinct spaces reconstructed from the capture.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    WALL LENGTH
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Metric distance between reconstructed wall endpoints.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    AREA
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Area enclosed by the reconstructed floor polygon.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    PERIMETER
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Sum of reconstructed room boundary lengths.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    CEILING HEIGHT
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Estimated vertical distance between detected floor and ceiling planes.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    OPENING
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Detected doorway/window associated with a wall and measured using 3D geometry.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    DAMAGE FINDING
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Visible defect classified from RGB imagery and associated with a surface.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                    SCOPE ITEM
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Suggested repair/action generated from detected damage and surface association.
                  </div>
                </div>
              </div>
            </section>

            {/* SECTION 7 — STATUS EXPLANATIONS */}
            <section id="statuses" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Understanding Statuses
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                Pipeline statuses describe whether COZMO produced a usable result:
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', padding: '12px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <StatusBadge status="COMPLETE" />
                  <div style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.45 }}>
                    <strong>COMPLETE:</strong> The pipeline produced a usable reconstruction.
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', padding: '12px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <StatusBadge status="PROVISIONAL" />
                  <div style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.45 }}>
                    <strong>PROVISIONAL:</strong> A reconstruction was produced, but one or more stages have limited evidence or reliability.
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', padding: '12px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <StatusBadge status="NOT_EVALUABLE" />
                  <div style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.45 }}>
                    <strong>NOT_EVALUABLE:</strong> The available input was insufficient to produce a trustworthy measurement/result.
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', padding: '12px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <StatusBadge status="FAILED" />
                  <div style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.45 }}>
                    <strong>FAILED:</strong> The reconstruction pipeline could not complete.
                  </div>
                </div>
              </div>

              <div className="callout-box warning">
                <strong>Important Distinction:</strong> Pipeline status describes whether COZMO produced a usable result. It does not by itself prove physical accuracy against independent ground truth.
              </div>
            </section>

            {/* SECTION 8 — MEASUREMENT / UNCERTAINTY EXPLANATION */}
            <section id="measurements" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Measurement & Uncertainty Explanation
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                COZMO presents both nominal measurements and estimated uncertainty ranges:
              </p>

              <div className="demo-grid-2" style={{ marginBottom: '16px' }}>
                <div style={{ padding: '16px', backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
                    Nominal Measurement
                  </div>
                  <div className="mono" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', margin: '4px 0' }}>
                    3.42 m
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    Fitted geometric endpoint-to-endpoint distance.
                  </div>
                </div>

                <div style={{ padding: '16px', backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
                    Estimated Range
                  </div>
                  <div className="mono" style={{ fontSize: '22px', fontWeight: 700, color: 'var(--primary)', margin: '4px 0' }}>
                    3.39 – 3.45 m
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    Estimated reconstruction uncertainty around the measurement.
                  </div>
                </div>
              </div>

              <div className="callout-box">
                <p style={{ margin: '0 0 6px 0', fontSize: '13px', lineHeight: 1.5 }}>
                  The range represents the reconstruction&apos;s estimated uncertainty around the measurement based on point cloud variance and plane fitting residuals.
                </p>
                <div style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>
                  Note: These ranges are currently uncalibrated against independent laser/tape ground truth.
                </div>
              </div>
            </section>

            {/* SECTION 9 — DRIFT EXPLANATION */}
            <section id="drift-reproducibility" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Understanding Drift & Drift Correction
              </h2>

              <div style={{ marginBottom: '14px' }}>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  What is drift?
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                  As the camera moves through multiple rooms, small pose errors accumulate over time, distorting the final multi-room property layout.
                </p>
              </div>

              <div style={{ marginBottom: '14px' }}>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  What COZMO does:
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                  COZMO executes <strong>Point-to-Plane ICP loop closure</strong> and <strong>global pose graph optimization</strong> to reconcile accumulated trajectory errors across revisit loops.
                </p>
              </div>

              <div style={{ marginBottom: '14px' }}>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Drift ablation:
                </div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                  We compare reconstruction behavior with drift correction enabled and disabled (e.g. <code>outputs/c7d28f72c6/property/drift_ablation.svg</code>).
                </p>
              </div>

              <div className="callout-box warning">
                <strong>Important Distinction:</strong> Internal loop residual minimization measures geometric closure consistency across scans; it is not the same as physical wall accuracy against independent laser ground truth.
              </div>
            </section>

            {/* SECTION 10 — REPRODUCIBILITY */}
            <section className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Reproducibility & Determinism
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '12px' }}>
                In verified reproducibility verification, the same supplied sample archives were uploaded twice through the live website. Fresh Upload A and Fresh Upload B produced identical meaningful geometry and results.
              </p>

              <div className="demo-grid-2" style={{ marginBottom: '12px' }}>
                <div style={{ padding: '12px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--success-text)', marginBottom: '2px' }}>
                    What this proves:
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Deterministic pipeline processing and state consistency.
                  </div>
                </div>

                <div style={{ padding: '12px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--danger-text)', marginBottom: '2px' }}>
                    What this does NOT prove:
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Physical measurement accuracy against real-world walls.
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>
                <em>No fixture substitution is used during these verification runs; all outputs are computed live.</em>
              </div>
            </section>

            {/* SECTION 11 — EXPORTS */}
            <section id="exports" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Export Formats
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                All exports are generated dynamically from the same current property result:
              </p>

              <div className="demo-grid-4">
                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <span className="mono" style={{ fontWeight: 700, fontSize: '14px', color: 'var(--primary)' }}>JSON</span>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Structured machine-readable reconstruction data with rooms, walls, openings, and 95% intervals.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <span className="mono" style={{ fontWeight: 700, fontSize: '14px', color: 'var(--primary)' }}>SVG</span>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Standalone 2D vector architectural floor plan with metric coordinates.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <span className="mono" style={{ fontWeight: 700, fontSize: '14px', color: 'var(--primary)' }}>PDF</span>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Multi-page readable inspection report with cover card, dimension schedules, and repair scope.
                  </div>
                </div>

                <div style={{ padding: '14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <span className="mono" style={{ fontWeight: 700, fontSize: '14px', color: 'var(--primary)' }}>DXF</span>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    CAD-compatible geometry export (Layered Release-12 standard for WALLS, OPENINGS, DIMENSIONS).
                  </div>
                </div>
              </div>
            </section>

            {/* SECTION 12 — WHAT DOES EACH EVALUATION PROVE? */}
            <section id="evaluations" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                What Does Each Evaluation Prove?
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                Clear breakdown of questions, required evidence, and honest status:
              </p>

              <div className="table-responsive">
                <table className="demo-table">
                  <thead>
                    <tr>
                      <th>Evaluation Target</th>
                      <th>Core Question</th>
                      <th>Required Evidence</th>
                      <th>Current Honest Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>Reproducibility</strong></td>
                      <td>Does the same input produce the same result?</td>
                      <td>Fresh Live Upload A vs Fresh Live Upload B</td>
                      <td><span style={{ color: 'var(--success-text)', fontWeight: 600 }}>PROVEN</span> (Identical geometry on identical inputs)</td>
                    </tr>
                    <tr>
                      <td><strong>Determinism</strong></td>
                      <td>Does internal pipeline randomness change geometry?</td>
                      <td>Repeated seed and processing runs</td>
                      <td><span style={{ color: 'var(--success-text)', fontWeight: 600 }}>PROVEN</span> (Zero drift on repeated fixed-seed runs)</td>
                    </tr>
                    <tr>
                      <td><strong>Drift Ablation</strong></td>
                      <td>Does drift correction improve multi-room consistency?</td>
                      <td>Trajectory comparison with/without loop closure</td>
                      <td><span style={{ color: 'var(--success-text)', fontWeight: 600 }}>VERIFIED</span> (Residual drop demonstrated on multi-room capture)</td>
                    </tr>
                    <tr>
                      <td><strong>Pipeline Tests</strong></td>
                      <td>Can each input tier produce a reconstruction?</td>
                      <td>LiDAR, Video (RGB-only), and Photo pipeline runs</td>
                      <td><span style={{ color: 'var(--success-text)', fontWeight: 600 }}>VERIFIED</span> (All 3 pipelines produce floor plans)</td>
                    </tr>
                    <tr>
                      <td><strong>Physical Accuracy</strong></td>
                      <td>How close are measurements to the real room?</td>
                      <td>Independent laser disto / steel tape ground truth</td>
                      <td><span style={{ color: 'var(--warning-text)', fontWeight: 600 }}>NOT EVALUABLE</span> (Laser GT not provided in sample data)</td>
                    </tr>
                    <tr>
                      <td><strong>Repeatability</strong></td>
                      <td>Do two genuinely separate captures match?</td>
                      <td>Two independent physical walkthroughs of same room</td>
                      <td><span style={{ color: 'var(--warning-text)', fontWeight: 600 }}>PENDING CAPTURE</span> (Requires 2 separate physical passes)</td>
                    </tr>
                    <tr>
                      <td><strong>Incumbent Comparison</strong></td>
                      <td>How does COZMO compare against another app?</td>
                      <td>Same physical room scanned with incumbent app + GT</td>
                      <td><span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>PENDING SCAN</span> (Benchmarking harness configured)</td>
                    </tr>
                    <tr>
                      <td><strong>Damage Benchmark</strong></td>
                      <td>Does pipeline detect and classify defects?</td>
                      <td>Defect fixture set with 3D projection</td>
                      <td><span style={{ color: 'var(--primary)', fontWeight: 600 }}>SYNTHETIC DEV</span> (Tested against synthetic development benchmark)</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            {/* SECTION 13 — RESULT STATUS VS BENCHMARK STATUS */}
            <section id="status-distinction" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Result Status vs Benchmark Status
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                Understanding why these two statuses are different and not contradictory:
              </p>

              <div className="demo-grid-2">
                <div style={{ padding: '16px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <StatusBadge status="COMPLETE" />
                    <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>Result Status</span>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    <strong>Means:</strong> A usable architectural floor plan was produced successfully from the available input sensor data.
                  </div>
                </div>

                <div style={{ padding: '16px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <StatusBadge status="NOT_EVALUABLE" />
                    <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>Benchmark Status</span>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    <strong>Means:</strong> Physical accuracy could not be mathematically scored because independent laser/tape ground truth was not provided.
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '12px' }}>
                These statuses are fully complementary: the software pipeline succeeded (COMPLETE), while the physical accuracy validation gate remains honestly unverified (NOT_EVALUABLE).
              </div>
            </section>

            {/* SECTION 14 — EVALUATOR QUICK TEST (5-MINUTE DEMO) */}
            <section id="quick-test" className="property-card" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                <span className="mono" style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'var(--primary-subtle)', color: 'var(--primary)', border: '1px solid var(--primary-border)' }}>
                  Fast Track
                </span>
                <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  5-Minute Evaluator Quick Test
                </h2>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                Follow these numbered steps for a rapid end-to-end evaluation:
              </p>

              <div className="demo-grid-2">
                {/* Frontend 5-min */}
                <div style={{ padding: '18px', backgroundColor: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)', marginBottom: '10px' }}>
                    Option A: Frontend (UI Flow)
                  </div>
                  <ol style={{ paddingLeft: '18px', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.7, margin: 0 }}>
                    <li>Start backend: <code className="mono">python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000</code></li>
                    <li>Start frontend: <code className="mono">cd frontend && npm run dev</code></li>
                    <li>Open <code className="mono">http://localhost:3000</code> in browser</li>
                    <li>Click <strong>New Capture</strong> button in top header</li>
                    <li>Select <strong>LiDAR</strong> capture tier</li>
                    <li>Choose file <code className="mono">sample data/single_room.zip</code></li>
                    <li>Click <strong>Process Capture</strong></li>
                    <li>Watch processing status transition to Complete</li>
                    <li>Click into the reconstructed room to inspect wall dimensions</li>
                    <li>Click <strong>Export</strong> to download PDF inspection report</li>
                  </ol>
                </div>

                {/* Backend 5-min */}
                <div style={{ padding: '18px', backgroundColor: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)', marginBottom: '10px' }}>
                    Option B: Backend (CLI Flow)
                  </div>
                  <ol style={{ paddingLeft: '18px', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.7, margin: 0 }}>
                    <li>Activate Python environment: <code className="mono">source .venv/bin/activate</code></li>
                    <li>Run verified single-room reconstruction:
                      <CommandBlock code={`python3 scripts/reconstruct_lidar.py --scan c00a170fe1 --archive "sample data/single_room.zip" --voxel-size 0.02`} />
                    </li>
                    <li>Inspect generated geometry: <code className="mono">outputs/c00a170fe1/measurements.json</code></li>
                    <li>Open generated vector floor plan: <code className="mono">outputs/c00a170fe1/structure_debug.svg</code></li>
                    <li>Review nominal wall lengths and estimated uncertainty intervals</li>
                  </ol>
                </div>
              </div>
            </section>

            {/* SECTION 15 — FULL DEMO */}
            <section id="full-demo" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Full Evaluation Workflow
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                To thoroughly evaluate all multimodal capabilities across the COZMO platform:
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ padding: '12px 14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '2px' }}>
                    1. LiDAR Multi-Room & Drift Correction
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    Run <code>python3 scripts/reconstruct_property.py --scan c7d28f72c6 --archive &quot;sample data/single_scan_with_ceiling.zip&quot; --headless</code> and review <code>outputs/c7d28f72c6/property/drift_ablation.svg</code>.
                  </div>
                </div>

                <div style={{ padding: '12px 14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '2px' }}>
                    2. Monocular Video Walkthrough
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    Run <code>python3 scripts/reconstruct_video.py --archive &quot;sample data/single_room.zip&quot; --scan c00a170fe1 --capture-id video_rec_01 --max-keyframes 30</code> and verify RGB-only feature matching and depth recovery.
                  </div>
                </div>

                <div style={{ padding: '12px 14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '2px' }}>
                    3. Room Photo Set
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    Run <code>python3 scripts/reconstruct_photos.py --input &quot;data/photo_dev/sample_room&quot; --capture-id photo_rec_01</code> and check resulting 2D room polygon.
                  </div>
                </div>

                <div style={{ padding: '12px 14px', backgroundColor: 'var(--surface-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', marginBottom: '2px' }}>
                    4. Forensic Damage Perception & Scope
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                    Run <code>python3 scripts/analyze_damage.py --capture-id c00a170fe1</code> to inspect classified defects and suggested repair scope.
                  </div>
                </div>
              </div>
            </section>

            {/* SECTION 16 — KNOWN LIMITATIONS */}
            <section id="limitations" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Known Limitations & Absolute Honesty Statement
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                In accordance with rigorous technical evaluation standards, known system boundaries are stated explicitly:
              </p>

              <ul style={{ paddingLeft: '18px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                <li><strong>No Independent Laser GT:</strong> Assessor sample data does not include certified laser/tape ground truth; all physical accuracy gates are marked <code className="mono">NOT_EVALUABLE</code>.</li>
                <li><strong>Photo Capture Format:</strong> Supplied archives do not contain native 2–8 still-photo capture sets; development evaluations used extracted still images and are explicitly labeled.</li>
                <li><strong>Reflective Surfaces:</strong> Glass walls, mirrors, and deep shadows can introduce depth gaps or noisy RANSAC planes.</li>
                <li><strong>Low-Texture Scenes:</strong> Video and photo SfM pipelines require sufficient visual feature texture for reliable camera pose estimation.</li>
                <li><strong>Ceiling Height Observation:</strong> Ceiling height estimation requires the sensor camera pitch to have observed the physical ceiling plane during the capture trajectory.</li>
                <li><strong>Uncertainty Calibration:</strong> Physical uncertainty ranges represent reconstruction variance and are uncalibrated against independent ground truth.</li>
              </ul>
            </section>

            {/* SECTION 17 — QUICK VERIFICATION CHECKLIST */}
            <section id="checklist" className="property-card" style={{ padding: '28px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Quick Verification Checklist
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" defaultChecked readOnly />
                  <span>Backend API health check responds at <code className="mono">http://localhost:8000/api/health</code></span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" defaultChecked readOnly />
                  <span>Frontend loads and renders workspaces at <code className="mono">http://localhost:3000</code></span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" defaultChecked readOnly />
                  <span>CLI reconstruction scripts execute cleanly and output JSON, SVG, and DXF</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" defaultChecked readOnly />
                  <span>Live upload workflow transitions from Queued → Processing → Complete</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" defaultChecked readOnly />
                  <span>Exports (JSON, SVG, PDF, DXF) generate cleanly from reconstructed properties</span>
                </label>
              </div>
            </section>

          </div>

          {/* Table of Contents Sticky Sidebar (Desktop Only) */}
          <aside className="demo-toc" aria-label="Table of Contents">
            <div
              style={{
                fontSize: '11px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                color: 'var(--text-muted)',
                marginBottom: '8px',
                paddingBottom: '6px',
                borderBottom: '1px solid var(--border)',
              }}
            >
              On This Page
            </div>

            <nav style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '12.5px' }}>
              <a href="#overview" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Overview
              </a>
              <a href="#choose-method" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Choose Method
              </a>
              <a href="#backend-demo" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Backend Demo
              </a>
              <a href="#frontend-demo" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Frontend Demo
              </a>
              <a href="#sample-data" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Sample Data
              </a>
              <a href="#results" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Understanding Results
              </a>
              <a href="#statuses" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Status Meanings
              </a>
              <a href="#measurements" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Measurements & Range
              </a>
              <a href="#drift-reproducibility" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Drift & Reproducibility
              </a>
              <a href="#exports" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Export Formats
              </a>
              <a href="#evaluations" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                What Evaluations Prove
              </a>
              <a href="#status-distinction" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Result vs Benchmark Status
              </a>
              <a href="#quick-test" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                5-Minute Quick Test
              </a>
              <a href="#full-demo" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Full Evaluation
              </a>
              <a href="#limitations" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Known Limitations
              </a>
              <a href="#checklist" style={{ padding: '4px 6px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
                Verification Checklist
              </a>
            </nav>
          </aside>
        </div>
      </main>
    </div>
  );
}
