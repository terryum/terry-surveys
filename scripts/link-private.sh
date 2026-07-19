#!/usr/bin/env bash
set -euo pipefail

echo "NOTE: scripts/link-private.sh is deprecated; survey content now lives in terry-surveys-contents." >&2
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/setup-contents.sh" "$@"
