#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q -r requirements.txt
python3 -m reelfx fonts
echo "reelfx ready."
