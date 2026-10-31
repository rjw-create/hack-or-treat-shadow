#!/usr/bin/env bash
# Verify everything that runs without a model: byte-compile, then unit and fake-model end-to-end tests.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi

echo "== compile"
"$PY" -m compileall -q shadow tests
echo "== tests"
"$PY" -m unittest discover -s tests -t . -v
echo "== all checks passed"
