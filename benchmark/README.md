# COZMO Benchmark & Validation Suite

## Directory Organization
- `ground_truth/`: Standardized JSON schemas and CSV/JSON templates for independent physical measurements.
- `benchmark_manifest.json`: Case registry linking raw capture archives, modalities, and physical GT contracts.
- `lidar/`: LiDAR pipeline performance, wall error distributions, ceiling measurements, and opening gates.
- `video/`: Monocular video SfM trajectory tracking, registration recovery, and relative error evaluation.
- `photo/`: Photo cluster multi-view geometry, scale estimation, and footprint relative error evaluation.
- `repeatability/`: Cross-capture consistency evaluation across identical physical environments (<= 1cm or 0.5%).
- `multiroom/`: Multi-room graph adjacency, boundary loop closure, drift ablation, and overlap checking.
- `damage/`: Damage classification, dimensional extent projection, and repair scope generation (labeled synthetic vs physical).
- `incumbent/`: 2-room comparative benchmarking protocol against market mobile scanners.
- `results/`: Output metrics (`metrics.json`, `gate_results.json`, `summary.csv`).
- `reports/`: Markdown benchmark evaluation reports.

## Running the Benchmark
Execute the automated runner from repo root:
```bash
python3 scripts/run_final_benchmark.py
```
Or with custom physical GT directory:
```bash
python3 scripts/run_final_benchmark.py --ground-truth /path/to/physical_gt_dir
```

## Absolute Honesty Policy
If physical ground-truth files (laser disto or steel tape audits) are absent on disk, all dependent accuracy gates strictly yield `NOT_EVALUABLE` or `PENDING_GT`. No synthetic or predicted values are substituted as ground truth.
