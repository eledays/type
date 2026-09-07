#!/usr/bin/env bash
set -euo pipefail

python -m pip_audit --strict --requirement requirements.txt
bandit --quiet --recursive app config.py
