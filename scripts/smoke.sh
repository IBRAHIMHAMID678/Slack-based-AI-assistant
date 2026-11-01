#!/usr/bin/env bash
# Headless smoke test script running the full proposal generation pipeline in mock mode
set -e

echo "=== Running Headless Smoke Test ==="
python scripts/smoke.py
echo "=== Smoke Test Complete ==="

