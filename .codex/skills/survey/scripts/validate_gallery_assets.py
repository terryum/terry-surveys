#!/usr/bin/env python3
"""Validate terryum-ai survey gallery cover/OG/thumb assets.

This catches mechanical asset drift plus the common survey-gallery style failure:
using a bright slide/infographic/screenshot as a thumbnail instead of the dark,
text-free, full-bleed visual style used by Terry's survey cards.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from PIL import Image


DEFAULT_TERRYUM_AI = Path("/Users/terrytaewoongum/Codes/personal/terryum-ai")

EXPECTED = {
    "cover": ("WEBP", (1200, 1200), "webp"),
    "og": ("PNG", (1200, 630), "png"),
    "thumb": ("WEBP", (288, 288), "webp"),
}


def asset_slug(slug: str) -> str:
    return slug if slug.startswith("survey-") else f"survey-{slug}"


def load_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def metrics(path: Path) -> dict[str, float]:
    img = load_rgb(path)
    small = img.resize((128, max(1, round(128 * img.height / img.width))))
    pix = list(small.getdata())
    count = len(pix)
    lumas = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b, _ in pix]
    near_white = sum(1 for r, g, b, a in pix if a > 0 and r > 220 and g > 220 and b > 220) / count
    white = sum(1 for r, g, b, a in pix if a > 0 and r > 240 and g > 240 and b > 240) / count
    dark = sum(1 for v in lumas if v < 80) / count

    w, h = small.size
    edge = max(4, round(min(w, h) * 0.08))
    border_pixels = []
    for y in range(h):
        for x in range(w):
            if x < edge or x >= w - edge or y < edge or y >= h - edge:
                border_pixels.append(small.getpixel((x, y)))
    border_count = len(border_pixels)
    border_near_white = (
        sum(1 for r, g, b, a in border_pixels if a > 0 and r > 220 and g > 220 and b > 220)
        / border_count
    )

    return {
        "mean_luma": statistics.mean(lumas),
        "near_white_ratio": near_white,
        "white_ratio": white,
        "dark_ratio": dark,
        "border_near_white_ratio": border_near_white,
    }


def validate_file(path: Path, kind: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{kind}: missing {path}"]

    expected_format, expected_size, expected_ext = EXPECTED[kind]
    if path.suffix.lower().lstrip(".") != expected_ext:
        errors.append(f"{kind}: expected .{expected_ext}, got {path.suffix}")

    with Image.open(path) as img:
        if img.format != expected_format:
            errors.append(f"{kind}: expected format {expected_format}, got {img.format}")
        if img.size != expected_size:
            errors.append(f"{kind}: expected {expected_size[0]}x{expected_size[1]}, got {img.size[0]}x{img.size[1]}")
        if "A" in img.getbands():
            alpha = img.getchannel("A")
            if alpha.getextrema()[0] < 255:
                errors.append(f"{kind}: has transparent pixels; gallery assets must be opaque")
    return errors


def baseline_cover_metrics(projects_dir: Path, target: str) -> list[float]:
    values = []
    for path in projects_dir.glob("survey-*-cover.webp"):
        if path.name == f"{target}-cover.webp":
            continue
        try:
            m = metrics(path)
        except Exception:
            continue
        # Exclude legacy non-survey or obviously bright assets from the style baseline.
        if m["near_white_ratio"] < 0.30:
            values.append(m["mean_luma"])
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", help="survey slug, e.g. large-data-manipulation or survey-large-data-manipulation")
    parser.add_argument("--terryum-ai-root", type=Path, default=DEFAULT_TERRYUM_AI)
    parser.add_argument("--style-only", action="store_true", help="skip file format/dimension checks")
    args = parser.parse_args()

    slug = asset_slug(args.slug)
    projects_dir = args.terryum_ai_root / "public" / "images" / "projects"
    paths = {
        "cover": projects_dir / f"{slug}-cover.webp",
        "og": projects_dir / f"{slug}-og.png",
        "thumb": projects_dir / f"{slug}-thumb.webp",
    }

    errors: list[str] = []
    if not args.style_only:
        for kind, path in paths.items():
            errors.extend(validate_file(path, kind))

    if not errors:
        cover = metrics(paths["cover"])
        thumb = metrics(paths["thumb"])
        baselines = baseline_cover_metrics(projects_dir, slug)
        median_luma = statistics.median(baselines) if baselines else 75.0
        luma_limit = max(125.0, median_luma + 55.0)

        print(
            f"cover: mean_luma={cover['mean_luma']:.1f}, near_white={cover['near_white_ratio']:.2%}, "
            f"border_near_white={cover['border_near_white_ratio']:.2%}, dark={cover['dark_ratio']:.2%}"
        )
        print(
            f"thumb: mean_luma={thumb['mean_luma']:.1f}, near_white={thumb['near_white_ratio']:.2%}, "
            f"dark={thumb['dark_ratio']:.2%}"
        )
        print(f"baseline median cover luma={median_luma:.1f}, limit={luma_limit:.1f}")

        if cover["mean_luma"] > luma_limit:
            errors.append(f"cover: too bright for survey gallery style ({cover['mean_luma']:.1f} > {luma_limit:.1f})")
        if cover["near_white_ratio"] > 0.28:
            errors.append(f"cover: near-white area too high ({cover['near_white_ratio']:.2%}); likely slide/screenshot")
        if cover["border_near_white_ratio"] > 0.30:
            errors.append(
                f"cover: bright border/background too high ({cover['border_near_white_ratio']:.2%}); use full-bleed dark visual"
            )
        if thumb["near_white_ratio"] > 0.28 or thumb["mean_luma"] > luma_limit:
            errors.append("thumb: inherits bright slide/screenshot style; regenerate from a dark text-free cover")

    if errors:
        print("BLOCKED: gallery asset style/spec failure", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("READY: gallery assets match survey card spec/style")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
