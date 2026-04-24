#!/usr/bin/env bash
# Link private surveys from the sibling `terry-private` repo into this monorepo.
#
# Private content (book/, docs/, assets/, scripts/, etc.) for restricted
# surveys (e.g. snu-tactile-hand) lives in ~/Codes/personal/terry-private/
# and never enters the public GitHub repo. This script restores symlinks so
# that `python3 build.py <slug>` and `bash surveys/<slug>/scripts/push.sh`
# keep working transparently after a fresh clone.
#
# Run this once after:
#   git clone git@github.com:terryum/terry-surveys.git
#   git clone git@github.com:terryum/terry-private.git ../terry-private
#
# Re-running is idempotent: existing symlinks are replaced, existing real
# directories are left untouched with a warning.
#
# Usage:
#   bash scripts/link-private.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIVATE_ROOT="$(cd "$ROOT/../terry-private" 2>/dev/null && pwd || echo '')"

if [ -z "$PRIVATE_ROOT" ] || [ ! -d "$PRIVATE_ROOT/surveys" ]; then
  echo "ERROR: expected a private overlay at ../terry-private/surveys" >&2
  echo "       clone it first: git clone git@github.com:terryum/terry-private.git ../terry-private" >&2
  exit 1
fi

count=0
for dir in "$PRIVATE_ROOT"/surveys/*/; do
  slug="$(basename "$dir")"
  link="$ROOT/surveys/$slug"
  target="../../terry-private/surveys/$slug"  # relative from surveys/<slug>

  if [ -L "$link" ]; then
    rm "$link"
  elif [ -e "$link" ]; then
    echo "SKIP surveys/$slug  (a real directory exists; refusing to replace)"
    continue
  fi

  ln -s "$target" "$link"
  echo "link surveys/$slug  →  terry-private/surveys/$slug"
  count=$((count + 1))
done

echo "done: $count survey(s) linked."
