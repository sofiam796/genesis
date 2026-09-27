#!/bin/bash
set -e

source venv/bin/activate

TOPIC="${1:-astronomy}"
LANGUAGES="${2:-uk}"
START="${3:-2024-09-01}"
END="${4:-2026-08-31}"
OUTPUT="${5:-output}"

python -m scripts.run_analysis \
  --topic "$TOPIC" \
  --topic-language en \
  --languages $LANGUAGES \
  --start "$START" \
  --end "$END" \
  --output "$OUTPUT"