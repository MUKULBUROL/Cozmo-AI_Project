# Incumbent Comparison Protocol (2-Room Benchmark)

## Overview
The challenge specification calls for benchmarking COZMO against an incumbent mobile scanning solution (e.g. Canvas / Polycam / Matterport / RoomPlan native) across at least 2 physical benchmark rooms.

## Evaluation Metric
Target criterion: COZMO beats or ties the incumbent scanner on **>= 70%** of shared dimensions against verified physical ground truth.

## Capture Instructions
1. Select 2 physical rooms with independently measured ground truth (via Leica Disto or calibrated steel tape).
2. Scan Room 1 and Room 2 with COZMO (LiDAR tier capture package).
3. Scan Room 1 and Room 2 with the incumbent mobile scanner on the identical iOS LiDAR device.
4. Export the resulting dimensions from both applications.
5. Populate `benchmark/incumbent/incumbent_measurements.csv` using the columns:
   `room_id,dimension_name,ground_truth_m,cozmo_predicted_m,incumbent_scanner_m,notes`
6. Execute the automated benchmark runner:
   `python3 scripts/run_final_benchmark.py --incumbent benchmark/incumbent/incumbent_measurements.csv`

## Current Benchmark Status
Status: `PENDING_INCUMBENT_CAPTURE`
Note: If raw incumbent scan outputs or physical room ground-truth measurements are not provided in the workspace repository, the benchmark runner strictly outputs `PENDING_INCUMBENT_CAPTURE` / `NOT_EVALUABLE` to prohibit fraudulent or fabricated competitive claims.
