#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTENTS_ROOT="$ROOT/../terry-surveys-contents"
CHECK_ONLY=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --check)
      CHECK_ONLY=true
      ;;
    --contents-root)
      shift
      CONTENTS_ROOT="${1:?--contents-root requires a path}"
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [ ! -d "$CONTENTS_ROOT/.git" ]; then
  echo "ERROR: private contents repository not found: $CONTENTS_ROOT" >&2
  echo "Clone it as a sibling: gh repo clone terryum/terry-surveys-contents ../terry-surveys-contents" >&2
  exit 1
fi

links=(
  "surveys|../terry-surveys-contents/surveys|surveys"
  "assets|../terry-surveys-contents/assets|assets"
  "bibtex/references.bib|../../terry-surveys-contents/bibtex/references.bib|bibtex/references.bib"
  "bibtex/refs_index.json|../../terry-surveys-contents/bibtex/refs_index.json|bibtex/refs_index.json"
  "bibtex/posts_index.json|../../terry-surveys-contents/bibtex/posts_index.json|bibtex/posts_index.json"
  "glossary/master_ko.md|../../terry-surveys-contents/glossary/master_ko.md|glossary/master_ko.md"
  "glossary/master_en.md|../../terry-surveys-contents/glossary/master_en.md|glossary/master_en.md"
)

failures=0
for spec in "${links[@]}"; do
  IFS='|' read -r path target contents_path <<< "$spec"
  destination="$ROOT/$path"
  source_path="$CONTENTS_ROOT/$contents_path"

  if [ ! -e "$source_path" ]; then
    echo "ERROR: contents path missing: $source_path" >&2
    failures=$((failures + 1))
    continue
  fi

  if [ -L "$destination" ] && [ "$(readlink "$destination")" = "$target" ]; then
    echo "ok    $path -> $target"
    continue
  fi

  if $CHECK_ONLY; then
    echo "ERROR: expected symlink: $path -> $target" >&2
    failures=$((failures + 1))
    continue
  fi

  if [ -e "$destination" ] || [ -L "$destination" ]; then
    echo "ERROR: refusing to replace non-canonical path: $destination" >&2
    failures=$((failures + 1))
    continue
  fi

  mkdir -p "$(dirname "$destination")"
  ln -s "$target" "$destination"
  echo "link  $path -> $target"
done

if [ "$failures" -ne 0 ]; then
  exit 1
fi

echo "survey contents workspace is ready"
