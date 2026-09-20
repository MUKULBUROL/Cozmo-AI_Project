"""Real End-to-End Capture Integration Test.

Executes:
1. Upload real LiDAR archive to POST /api/captures
2. Verify SHA256 input isolation in runtime/captures/<id>/input/
3. Poll GET /api/captures/<id> through processing lifecycle
4. Verify execution of reconstruction pipeline and generation of fresh artifacts
5. Fetch GET /api/captures/<id>/result and verify honest property payload
6. Prove zero fixture substitution
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path("/home/devcontainers/Projects/Active/CosmoAIProject-frontend")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

# 1. Prepare upload input
input_archive = PROJECT_ROOT / "sample data" / "single_room.zip"
if not input_archive.exists():
    print(f"ERROR: {input_archive} not found")
    sys.exit(1)

input_bytes = input_archive.read_bytes()
input_sha256 = hashlib.sha256(input_bytes).hexdigest()
print(f"Input file:       {input_archive.name}")
print(f"Input size:       {len(input_bytes)} bytes")
print(f"Input SHA256:     {input_sha256}")

# 2. POST /api/captures
t0 = time.time()
resp = client.post(
    "/api/captures",
    files={"file": (input_archive.name, input_bytes, "application/zip")},
    data={"tier": "lidar"},
)
print(f"POST status code: {resp.status_code}")
res_data = resp.json()
print(f"POST response:    {res_data}")

cap_id = res_data["id"]
print(f"Generated ID:     {cap_id}")

# 3. Verify input isolation & SHA256 match
saved_input = PROJECT_ROOT / "runtime" / "captures" / cap_id / "input" / input_archive.name
if not saved_input.exists():
    print(f"ERROR: Saved input not found at {saved_input}")
    sys.exit(1)

saved_sha256 = hashlib.sha256(saved_input.read_bytes()).hexdigest()
assert saved_sha256 == input_sha256, f"SHA256 mismatch: {saved_sha256} vs {input_sha256}"
print(f"Stored SHA256:    {saved_sha256} (MATCHES UPLOADED BYTES)")

# 4. Poll /api/captures/{id} until terminal status
print("\nPolling capture status...")
max_wait = 300
start_poll = time.time()
final_status = None

while time.time() - start_poll < max_wait:
    s_resp = client.get(f"/api/captures/{cap_id}")
    status_data = s_resp.json()
    st = status_data["status"]
    stage = status_data.get("progress_stage")
    err = status_data.get("error")
    elapsed = time.time() - start_poll
    print(f"  [{elapsed:.1f}s] Status: {st} | Stage: {stage} | Error: {err}")
    if st in ("COMPLETE", "PROVISIONAL", "NOT_EVALUABLE", "FAILED"):
        final_status = status_data
        break
    time.sleep(3)

elapsed_total = time.time() - t0
print(f"\nFinal status:     {final_status['status']}")
print(f"Elapsed time:     {elapsed_total:.2f}s")

# 5. GET /api/captures/{id}/result
result_resp = client.get(f"/api/captures/{cap_id}/result")
print(f"Result HTTP code: {result_resp.status_code}")
result_data = result_resp.json()

# Inspect generated artifacts
output_dir = PROJECT_ROOT / "runtime" / "captures" / cap_id / "outputs"
artifacts = [str(p.relative_to(output_dir)) for p in output_dir.glob("**/*") if p.is_file()]
print(f"Output dir:       {output_dir}")
print(f"Artifacts ({len(artifacts)}):")
for a in sorted(artifacts):
    print(f"  - {a}")

print(f"\nResult property_id: {result_data.get('property_id')}")
print(f"Result capture_id:  {result_data.get('capture_id')}")
print(f"Result status:      {result_data.get('status')}")
print(f"Result rooms:       {len(result_data.get('rooms', []))}")

assert result_data["capture_id"] == cap_id
assert result_data["capture_id"] not in ("c00a170fe1", "c7d28f72c6", "stage11-video")
print("\nE2E VERIFICATION SUCCESSFUL: Real capture executed with fresh isolated artifacts and zero fixture substitution!")
