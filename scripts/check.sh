#!/usr/bin/env bash
# Vérification complète, sans GPU, sans modèle, sans carte son : à faire passer avant chaque commit.
# Une seule définition pour le hook pre-commit, `scripts/feature.sh pr` et la CI.
#   scripts/check.sh          lint, format, tests
#   scripts/check.sh --fix    applique d'abord le formatage et les corrections sûres de ruff
set -euo pipefail
cd "$(dirname "$0")/.."
FIX=0
for a in "$@"; do
  case $a in
    --fix) FIX=1 ;;
    *) echo "option inconnue : $a" >&2; exit 2 ;;
  esac
done
step() { printf '\n== %s\n' "$*"; }

if [[ -z ${CI:-} && ! -x $(git rev-parse --git-path hooks)/pre-push ]]; then
  echo "⚠ hooks git non installés : scripts/install-hooks.sh (cycle PR imposé)"
fi

if (( FIX )); then
  step "corrections"
  uv run -q ruff check --fix -q .
  uv run -q ruff format -q .
fi

step "lint"
uv run -q ruff check .

step "format"
uv run -q ruff format --check .

step "tests (sans GPU, sans modèle, sans carte son)"
uv run -q pytest -q

printf '\nOK\n'
