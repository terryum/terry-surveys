#!/usr/bin/env python3
"""Generate a deterministic manifest for local-only survey assets."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    contents = Path(sys.argv[1] if len(sys.argv) > 1 else "../terry-surveys-contents").resolve()
    surveys = contents / "surveys"
    if not surveys.is_dir():
        raise SystemExit(f"survey contents directory not found: {surveys}")
    rows = []
    for asset_dir in sorted(surveys.glob("*/assets")):
        slug = asset_dir.parent.name
        for path in sorted(item for item in asset_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(contents).as_posix()
            rows.append({
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "r2_key": f"survey-assets/{slug}/assets/{path.relative_to(asset_dir).as_posix()}",
            })
    payload = {
        "schema_version": "1.0",
        "storage": "private-cloudflare-r2",
        "assets": rows,
        "asset_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
    }
    output = contents / "assets/manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output}: {len(rows)} assets, {payload['total_bytes']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
