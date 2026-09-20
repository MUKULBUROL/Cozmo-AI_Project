/**
 * @file new/page.tsx
 * @purpose Live capture upload page with tier selection, file validation, and FastAPI submission.
 * @stage Frontend Stage 3 — Live FastAPI Integration.
 * @inputs User-selected tier and file upload.
 * @outputs Creates a new capture job via POST /api/captures, redirects to /processing/[id].
 * @dependencies next/navigation, ../../lib/api/captures, ../../lib/api/errors.
 * @assumptions FastAPI backend is running at NEXT_PUBLIC_API_BASE_URL. File validation mirrors backend expectations.
 * @failureModes Network errors show inline error message. Invalid files show validation message before upload.
 * @firstDebuggingPoints Check browser Network tab for POST request. Verify API URL in .env.local. Check console for errors.
 */

'use client';

import React, { useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createCapture, getAcceptedFileTypes } from '../../lib/api/captures';
import type { ReconstructionTier } from '../../domain/types';

type UploadState = 'idle' | 'validating' | 'uploading' | 'error';

export default function NewCapturePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedTier, setSelectedTier] = useState<ReconstructionTier>('lidar');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const tiers: Array<{
    id: ReconstructionTier;
    title: string;
    description: string;
    features: string[];
    badge: string;
    acceptedFormats: string;
  }> = [
    {
      id: 'lidar',
      title: 'LiDAR Reconstruction',
      badge: 'High Precision',
      description: 'Metric unprojection from ARKit depth frames with deterministic RANSAC extraction.',
      features: ['Sub-cm point cloud resolution', 'Direct metric scale', 'Ceiling & floor height separation'],
      acceptedFormats: 'ZIP archive with odometry.csv',
    },
    {
      id: 'video',
      title: 'RGB Video SfM',
      badge: 'Stage 11 Metric Scale',
      description: 'Continuous video keyframe tracking with Depth Anything v2 metric unprojection.',
      features: ['Multi-view feature matching', 'Temporal continuity audit', 'Provisional plan topology'],
      acceptedFormats: 'MP4 video or ZIP with rgb.mp4',
    },
    {
      id: 'photo',
      title: 'Multi-View Photo Set',
      badge: 'Sparse Alignment',
      description: 'Uncalibrated photo set reconstruction with COLMAP structure-from-motion.',
      features: ['Ordered perspective matching', 'Requires visual overlap > 60%', 'Uncalibrated baseline'],
      acceptedFormats: 'ZIP archive of JPEG/PNG images',
    },
  ];

  const handleTierChange = useCallback((tier: ReconstructionTier) => {
    setSelectedTier(tier);
    setSelectedFile(null);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMessage(null);
    const file = e.target.files?.[0] || null;
    if (!file) {
      setSelectedFile(null);
      return;
    }

    // Client-side extension validation
    const ext = '.' + (file.name.split('.').pop()?.toLowerCase() || '');
    const accepted = getAcceptedFileTypes(selectedTier).split(',');
    if (!accepted.includes(ext)) {
      setErrorMessage(
        `${selectedTier.toUpperCase()} tier does not accept ${ext} files. Accepted: ${accepted.join(', ')}.`
      );
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  }, [selectedTier]);

  const handleSubmit = async () => {
    if (!selectedFile) return;

    setUploadState('validating');
    setErrorMessage(null);

    try {
      setUploadState('uploading');
      const result = await createCapture(selectedTier, selectedFile);
      // Redirect to processing page with new capture ID
      router.push(`/processing/${result.id}`);
    } catch (err) {
      setUploadState('error');
      setErrorMessage(
        err instanceof Error ? err.message : 'Upload failed. Please check that the API server is running.'
      );
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--background)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Top Header */}
      <header
        style={{
          height: 'var(--topbar-height)',
          backgroundColor: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 32px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link
            href="/"
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            ← Back to Workspaces
          </Link>
          <span style={{ color: 'var(--border-strong)' }}>/</span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            New Capture
          </span>
        </div>
      </header>

      {/* Main Container */}
      <main
        style={{
          maxWidth: '780px',
          width: '100%',
          margin: '40px auto',
          padding: '0 24px',
        }}
      >
        <div style={{ marginBottom: '28px' }}>
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 700,
              color: 'var(--text-primary)',
              letterSpacing: '-0.02em',
              marginBottom: '6px',
            }}
          >
            Select Reconstruction Sensor Tier
          </h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Choose the capture methodology matching your input data, then upload your capture file for processing.
          </p>
        </div>

        {/* Tier Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '32px' }}>
          {tiers.map((t) => {
            const isSelected = selectedTier === t.id;
            return (
              <div
                key={t.id}
                role="radio"
                aria-checked={isSelected}
                aria-label={`${t.title} tier`}
                tabIndex={0}
                onClick={() => handleTierChange(t.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleTierChange(t.id);
                  }
                }}
                style={{
                  backgroundColor: 'var(--surface)',
                  border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '20px 24px',
                  cursor: 'pointer',
                  boxShadow: isSelected ? 'var(--shadow-md)' : 'var(--shadow-sm)',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {t.title}
                    </h2>
                    <span
                      style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--surface-subtle)',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border)',
                        fontWeight: 500,
                      }}
                    >
                      {t.badge}
                    </span>
                  </div>

                  <div
                    style={{
                      width: '18px',
                      height: '18px',
                      borderRadius: '50%',
                      border: isSelected ? '5px solid var(--primary)' : '2px solid var(--border-strong)',
                      backgroundColor: 'var(--surface)',
                    }}
                  />
                </div>

                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: 1.4 }}>
                  {t.description}
                </p>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '6px' }}>
                  {t.features.map((feat, idx) => (
                    <span
                      key={idx}
                      style={{
                        fontSize: '12px',
                        color: 'var(--text-muted)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <span style={{ color: 'var(--success)' }}>✓</span> {feat}
                    </span>
                  ))}
                </div>

                <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  Accepted: {t.acceptedFormats}
                </div>
              </div>
            );
          })}
        </div>

        {/* Upload Area */}
        <div
          style={{
            backgroundColor: 'var(--surface)',
            border: selectedFile ? '2px solid var(--primary)' : '1px dashed var(--border-strong)',
            borderRadius: 'var(--radius-md)',
            padding: '32px',
            textAlign: 'center',
            marginBottom: '16px',
          }}
        >
          {!selectedFile ? (
            <>
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--surface-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px auto',
                  color: 'var(--text-muted)',
                }}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>

              <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                Upload Capture File
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Select a {selectedTier.toUpperCase()} capture file to begin reconstruction.
              </p>

              <input
                ref={fileInputRef}
                type="file"
                accept={getAcceptedFileTypes(selectedTier)}
                onChange={handleFileSelect}
                id="capture-file-input"
                style={{ display: 'none' }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                aria-label="Choose capture file"
                style={{
                  padding: '9px 20px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--primary)',
                  color: 'var(--text-on-primary)',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Choose File
              </button>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', marginBottom: '16px' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {selectedFile.name}
                  </div>
                  <div className="mono" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    {formatFileSize(selectedFile.size)} · {selectedTier.toUpperCase()} tier
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                <button
                  onClick={() => {
                    setSelectedFile(null);
                    setErrorMessage(null);
                    setUploadState('idle');
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--surface-subtle)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Change File
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={uploadState === 'uploading'}
                  aria-label="Submit capture for processing"
                  style={{
                    padding: '8px 20px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: uploadState === 'uploading' ? 'var(--surface-subtle)' : 'var(--primary)',
                    color: uploadState === 'uploading' ? 'var(--text-muted)' : 'var(--text-on-primary)',
                    border: 'none',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: uploadState === 'uploading' ? 'not-allowed' : 'pointer',
                  }}
                >
                  {uploadState === 'uploading' ? 'Uploading…' : 'Submit for Processing'}
                </button>
              </div>
            </>
          )}
        </div>

        {/* Error Message */}
        {errorMessage && (
          <div
            role="alert"
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--danger-subtle, #fef2f2)',
              border: '1px solid var(--danger-border, #fecaca)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--danger-text, #dc2626)',
              fontSize: '13px',
              lineHeight: 1.5,
              marginBottom: '16px',
            }}
          >
            {errorMessage}
          </div>
        )}

        <div style={{ textAlign: 'center' }}>
          <Link
            href="/"
            style={{
              fontSize: '13px',
              color: 'var(--primary)',
              fontWeight: 500,
            }}
          >
            ← Or explore existing benchmark captures
          </Link>
        </div>
      </main>
    </div>
  );
}
