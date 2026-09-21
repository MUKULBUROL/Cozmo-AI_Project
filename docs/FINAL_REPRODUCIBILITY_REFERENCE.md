# Final Reproducibility Reference Outputs

This document records the canonical reference results for the three assessor-provided LiDAR sample datasets before executing the fresh website upload verification protocol.

---

## 1. Multi-Room LiDAR Scan with Ceiling (`c7d28f72c6`)

- **Source Archive**: `sample data/single_scan_with_ceiling.zip`
- **Scan ID**: `c7d28f72c6`
- **SHA256**: `4bfbeb11ee21b114c46ad43cf0c9602d8ada827397f4e8b3c70dd827d0191379`
- **Canonical Reference Artifact**: `outputs/c7d28f72c6/property/property.json`
- **Pipeline / Command**: `python3 -m scripts.reconstruct_property --scan c7d28f72c6 --archive "sample data/single_scan_with_ceiling.zip" --headless`
- **Git Commit Baseline**: `4690fee` (`feat/final-evidence-verification`)
- **Reconstruction Status**: `COMPLETE` / `IMPROVED` (Optimization Residual: `0.0033 m`, 96.4% improvement)
- **Room Count**: 4 (3 main rooms + 1 hallway connector)
- **Wall Count**: 20 total bounding walls (6 in Room 01, 4 in Room 02, 6 in Room 03, 4 in Connector 01)
- **Opening Count**: 0 structural threshold breaches
- **Damage Count**: 0 (undamaged capture)
- **Total Floor Area**: `72.00 m²`
  - Room 01: `24.57 m²`
  - Room 02: `16.86 m²`
  - Room 03: `17.03 m²`
  - Connector 01: `13.54 m²`
- **Total Perimeter**: `69.26 m`
- **Ceiling Height**: `3.35 m` (or `3.428 m` under Stage 6 structural plane detection)
- **Topological Adjacency Edges**: 4 (planar non-overlapping adjacency graph)

---

## 2. Single Room LiDAR Scan (`c00a170fe1`)

- **Source Archive**: `sample data/single_room.zip`
- **Scan ID**: `c00a170fe1`
- **SHA256**: `0805f742d378e4bda480fef6e5839304364807bb7b77bb459983003727e9699c`
- **Canonical Reference Artifact**: `outputs/c00a170fe1/` (`outputs/c00a170fe1/measurements/measurements.json` & `outputs/c00a170fe1/floorplan_geometry/room_polygon.json`)
- **Pipeline / Command**: `python3 -m scripts.reconstruct_property --scan c00a170fe1 --archive "sample data/single_room.zip" --headless`
- **Git Commit Baseline**: `4690fee` (`feat/final-evidence-verification`)
- **Reconstruction Status**: `PROVISIONAL` / `COMPLETE`
- **Room Count**: 1 Room primary polygon (or 3 segmented zones with hallway connector under global property multi-room mode)
- **Wall Count**: 4 dominant structural walls (7 to 9 projected wall segments in detailed single-room polygon)
- **Opening Count**: 1 doorway opening (`opening_01`, width `0.80 m` to `0.86 m`)
- **Damage Count**: 3 detected annotations (`dmg_c00a170fe1_01`, `02`, `03` - water stains / hairline plaster cracking)
- **Total Floor Area**: `4.65 m²` to `5.12 m²`
- **Perimeter**: `8.68 m` to `9.14 m`
- **Ceiling Height**: `null` / `UNOBSERVED` (scan camera pitch was horizontal/downward; ceiling unobserved)

---

## 3. Floor-Only Single Scan (`1a8384c3f6`)

- **Source Archive**: `sample data/single_scan_floor_only.zip`
- **Scan ID**: `1a8384c3f6`
- **SHA256**: `f822287268297d2adab49deff8e0ee5f50f05304b450d8d47d0b5eb476aa74d4`
- **Canonical Reference Artifact**: `outputs/1a8384c3f6/` & multi-room baseline property
- **Pipeline / Command**: `python3 -m scripts.reconstruct_property --scan 1a8384c3f6 --archive "sample data/single_scan_floor_only.zip" --headless`
- **Git Commit Baseline**: `4690fee` (`feat/final-evidence-verification`)
- **Reconstruction Status**: `COMPLETE` / `IMPROVED` (Optimization Residual: `0.0006 m`, 98.2% improvement)
- **Room Count**: 4 (3 rooms + 1 hallway connector)
- **Wall Count**: 8 dominant structural walls
- **Opening Count**: 0 detected openings
- **Damage Count**: 0 (undamaged capture)
- **Ceiling Height**: `null` / `UNOBSERVED` (floor-only camera trajectory)
