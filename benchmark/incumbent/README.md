# Incumbent Scanner Comparison Protocol (2-Room Benchmark)

## Overview
The challenge specification calls for benchmarking COZMO against an incumbent mobile scanning solution (e.g. Canvas, Polycam, or Apple RoomPlan) across at least **2 physical benchmark rooms**.

---

## 2-Room Human Capture Workflow

### Room 1 Workflow:
1. **Independent Ground Truth**: Measure all wall lengths, ceiling height, and door/window openings using a calibrated laser distance meter (e.g. Leica DISTO D2) or certified steel tape.
2. **COZMO Capture**: Perform an iOS LiDAR capture using the COZMO pipeline. Process and record resulting dimensions.
3. **Incumbent Capture**: Perform an iOS LiDAR capture of the exact same room using the incumbent scanner application. Export and record resulting dimensions.

### Room 2 Workflow:
1. Repeat the exact 3-step sequence for the second physical room (e.g., Office/Bedroom).

---

## Evaluation Metric & Required Comparison Table

### Gate Target:
COZMO beats or ties the incumbent scanner on **>= 70%** of shared dimensions evaluated against verified physical ground truth.

### Required Comparison Table Format:

| room | measurement | GT (m) | COZMO (m) | COZMO_error (m) | incumbent (m) | incumbent_error (m) | better_or_tie |
|---|---|---|---|---|---|---|---|
| room_01 | wall_north | 5.420 | 5.424 | 0.004 | 5.435 | 0.015 | YES |
| room_01 | wall_east | 4.485 | 4.490 | 0.005 | 4.470 | 0.015 | YES |
| room_01 | ceiling_height | 2.450 | 2.452 | 0.002 | 2.435 | 0.015 | YES |
| room_02 | wall_north | 3.800 | 3.805 | 0.005 | 3.790 | 0.010 | YES |
| room_02 | wall_east | 3.200 | 3.195 | 0.005 | 3.220 | 0.020 | YES |
| room_02 | ceiling_height | 2.450 | 2.448 | 0.002 | 2.465 | 0.015 | YES |

*(Note: The table above illustrates the required schema; no measurements may be fabricated without live captures).*

---

## Ingestion & Automated Runner

1. Populate `benchmark/incumbent/incumbent_measurements.csv` with real human collected data.
2. Execute the benchmark suite:
   ```bash
   python3 scripts/run_final_benchmark.py --gt-dir benchmark/ground_truth --incumbent benchmark/incumbent/incumbent_measurements.csv
   ```
3. When incumbent measurements are absent, the runner strictly outputs `PENDING_INCUMBENT` / `NOT_EVALUABLE`.
