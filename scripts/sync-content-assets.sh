#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTENTS_ROOT="$ROOT/../terry-surveys-contents"
ENV_FILE="$ROOT/../terryum-ai/.env.local"
BUCKET="${SURVEY_R2_BUCKET_NAME:-terry-surveys-assets-private}"
MODE="${1:-}"
DRY_RUN=false

shift || true
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --contents-root=*) CONTENTS_ROOT="${1#--contents-root=}" ;;
    --env-file=*) ENV_FILE="${1#--env-file=}" ;;
    --bucket=*) BUCKET="${1#--bucket=}" ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$MODE" = "manifest" ]; then
  exec python3 "$ROOT/scripts/generate-asset-manifest.py" "$CONTENTS_ROOT"
fi
if [ "$MODE" != "upload" ] && [ "$MODE" != "download" ] && [ "$MODE" != "ensure-bucket" ] && [ "$MODE" != "verify" ]; then
  echo "Usage: $0 <manifest|ensure-bucket|upload|download|verify> [--dry-run] [--contents-root=PATH] [--env-file=PATH] [--bucket=NAME]" >&2
  exit 2
fi
if [ ! -d "$CONTENTS_ROOT/surveys" ]; then
  echo "ERROR: contents repository not found: $CONTENTS_ROOT" >&2
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: R2 environment file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a
: "${R2_ACCOUNT_ID:?R2_ACCOUNT_ID is required}"
: "${R2_ACCESS_KEY_ID:?R2_ACCESS_KEY_ID is required}"
: "${R2_SECRET_ACCESS_KEY:?R2_SECRET_ACCESS_KEY is required}"

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION=auto
ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

if [ "$MODE" = "ensure-bucket" ]; then
  if aws s3api head-bucket --bucket "$BUCKET" --endpoint-url "$ENDPOINT" >/dev/null 2>&1; then
    echo "private R2 bucket exists: $BUCKET"
  else
    aws s3api create-bucket --bucket "$BUCKET" --endpoint-url "$ENDPOINT" >/dev/null
    echo "created private R2 bucket: $BUCKET"
  fi
  exit 0
fi

if [ "$MODE" = "verify" ]; then
  manifest="$CONTENTS_ROOT/assets/manifest.json"
  if [ ! -f "$manifest" ]; then
    echo "ERROR: asset manifest missing: $manifest" >&2
    exit 1
  fi
  read -r expected_count expected_bytes <<< "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["asset_count"], d["total_bytes"])' "$manifest")"
  read -r remote_count remote_bytes <<< "$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix survey-assets/ --endpoint-url "$ENDPOINT" --query '[length(Contents), sum(Contents[].Size)]' --output text)"
  if [ "$expected_count" != "$remote_count" ] || [ "$expected_bytes" != "$remote_bytes" ]; then
    echo "ERROR: R2 asset totals differ from manifest (expected $expected_count/$expected_bytes, remote $remote_count/$remote_bytes)" >&2
    exit 1
  fi
  echo "verified private R2 assets: $remote_count files, $remote_bytes bytes"
  exit 0
fi

if [ "$MODE" = "upload" ]; then
  python3 "$ROOT/scripts/generate-asset-manifest.py" "$CONTENTS_ROOT"
fi

count=0
for survey_dir in "$CONTENTS_ROOT"/surveys/*/; do
  slug="$(basename "$survey_dir")"
  local_assets="$survey_dir/assets"
  if [ "$MODE" = "upload" ] && [ ! -d "$local_assets" ]; then
    continue
  fi
  mkdir -p "$local_assets"
  remote="s3://$BUCKET/survey-assets/$slug/assets/"
  echo "$MODE $slug assets"
  if [ "$MODE" = "upload" ]; then
    if $DRY_RUN; then
      aws s3 sync "$local_assets/" "$remote" --endpoint-url "$ENDPOINT" --exclude '.DS_Store' --no-progress --only-show-errors --dryrun
    else
      aws s3 sync "$local_assets/" "$remote" --endpoint-url "$ENDPOINT" --exclude '.DS_Store' --no-progress --only-show-errors
    fi
  else
    if $DRY_RUN; then
      aws s3 sync "$remote" "$local_assets/" --endpoint-url "$ENDPOINT" --exclude '.DS_Store' --no-progress --only-show-errors --dryrun
    else
      aws s3 sync "$remote" "$local_assets/" --endpoint-url "$ENDPOINT" --exclude '.DS_Store' --no-progress --only-show-errors
    fi
  fi
  count=$((count + 1))
done

echo "$MODE complete: $count survey asset directorie(s), bucket=$BUCKET"
