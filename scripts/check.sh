#!/usr/bin/env bash
# Verify everything that runs without a model: byte-compile, then unit and fake-model end-to-end tests.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi

echo "== compile"
"$PY" -m compileall -q shadow tests
if [ "${1:-}" = "--fast" ]; then
  # End-to-end modules drive a real browser (about 74 of the 80 s on an idle machine). Add new ones here.
  slow="tests/test_evals_runner.py tests/test_run_fake.py"
  mods=""
  for f in tests/test_*.py; do
    case " $slow " in *" $f "*) ;; *) mods="$mods $(echo "$f" | sed 's#/#.#; s#\.py$##')" ;; esac
  done
  echo "== tests (fast: end-to-end browser tests skipped; run without --fast before a PR)"
  "$PY" -m unittest $mods
  echo "== fast checks passed"
  exit 0
fi
echo "== tests"
"$PY" -m unittest discover -s tests -t . -v
echo "== all checks passed"
