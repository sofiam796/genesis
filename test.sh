#!/bin/bash
set -e

source venv/bin/activate

python -m pytest
RUN_NETWORK_TESTS=1 python -m pytest