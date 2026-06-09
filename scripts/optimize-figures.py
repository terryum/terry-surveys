#!/usr/bin/env python3
"""Opt-in figure compression for terry-surveys docs/ build output.

Gemini 3 Pro Image always returns 2K PNG (~2-3 MB each). For surveys with
many illustrations this balloons to >100 MB of static assets. This script
compresses docs/assets/figures/*.{png,jpg,jpeg} in place or alongside, never
touching the source-of-truth files at surveys/<name>/assets/.

Usage:
    python3 scripts/optimize-figures.py <survey-name>
    python3 scripts/optimize-figures.py --all
    python3 scripts/optimize-figures.py --dry-run <survey-name>
    python3 scripts/optimize-figures.py --inplace-jpeg <survey-name>

Default (alongside): emits same-stem .webp (q82) and .jpg (q85) next to the
original PNG/JPEG. Originals are left untouched. HTML references continue
to point at the originals; future <picture>-tag work is a separate PR.

--inplace-jpeg: replaces large PNGs with same-stem .jpg, updates every
docs/**/*.html reference from <stem>.png → <stem>.jpg, and removes the
original PNG. Use this when you want immediate page-load win and the
figures don't require lossless fidelity. SVG/PDF/GIF are always skipped.

Re-running after `python3 build.py <name>` is required because build copies
fresh originals from surveys/<name>/assets/figures into docs/.
"""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.stderr.write(
        "ERROR: Pillow is required. Install with: pip install Pillow\n"
    )
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
SURVEYS_DIR = REPO_ROOT / 'surveys'

SIZE_THRESHOLD = 2 * 1024 * 1024  # 2 MiB — smaller files don't justify churn
WEBP_QUALITY = 82
JPEG_QUALITY = 85
TARGET_EXTS = {'.png', '.jpg', '.jpeg'}


def human(n_bytes):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n_bytes < 1024:
            return f"{n_bytes:.1f}{unit}"
        n_bytes /= 1024
    return f"{n_bytes:.1f}TB"


def flatten_to_rgb(img):
    """Drop alpha by compositing onto white — JPEG has no alpha channel."""
    if img.mode in ('RGBA', 'LA'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    if img.mode != 'RGB':
        return img.convert('RGB')
    return img


def list_target_figures(survey_name):
    figures_dir = SURVEYS_DIR / survey_name / 'docs' / 'assets' / 'figures'
    if not figures_dir.is_dir():
        return []
    targets = []
    for entry in sorted(figures_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in TARGET_EXTS:
            continue
        if entry.stat().st_size < SIZE_THRESHOLD:
            continue
        targets.append(entry)
    return targets


def emit_alongside(path, dry_run):
    """Generate <stem>.webp and <stem>.jpg next to path. Returns saved bytes."""
    original_size = path.stat().st_size
    stem_dir = path.parent
    stem = path.stem

    webp_out = stem_dir / f"{stem}.webp"
    jpg_out = stem_dir / f"{stem}.jpg"

    if dry_run:
        print(f"  [dry] would emit {webp_out.name} + {jpg_out.name} "
              f"(from {path.name}, {human(original_size)})")
        return 0

    with Image.open(path) as img:
        flat = flatten_to_rgb(img)
        flat.save(webp_out, 'WEBP', quality=WEBP_QUALITY, method=6)
        # Skip writing .jpg if the source already is the .jpg target
        if jpg_out.name != path.name:
            flat.save(jpg_out, 'JPEG', quality=JPEG_QUALITY, optimize=True)

    new_total = webp_out.stat().st_size
    if jpg_out.exists() and jpg_out != path:
        new_total += jpg_out.stat().st_size
    delta = original_size - min(webp_out.stat().st_size,
                                jpg_out.stat().st_size if jpg_out.exists() else 10**12)
    print(f"  {path.name} ({human(original_size)}) → "
          f"{webp_out.name} ({human(webp_out.stat().st_size)})"
          + (f", {jpg_out.name} ({human(jpg_out.stat().st_size)})"
             if jpg_out.exists() and jpg_out != path else ""))
    return max(delta, 0)


def rewrite_html_refs(docs_dir, replacements, dry_run):
    """Update every <img src> / href / url() to swap original → new filename.

    replacements: list of (old_basename, new_basename) tuples.
    Scans .html/.css/.js under docs_dir. We do a literal string replace because
    figure filenames are unique enough (chNN_*) that false positives are
    extremely unlikely, and regex on every HTML file would be slow.
    """
    if not replacements:
        return 0
    touched = 0
    for root, _, files in os.walk(docs_dir):
        for fname in files:
            if not fname.endswith(('.html', '.css', '.js')):
                continue
            p = Path(root) / fname
            try:
                text = p.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            new_text = text
            for old, new in replacements:
                if old in new_text:
                    new_text = new_text.replace(old, new)
            if new_text != text:
                if not dry_run:
                    p.write_text(new_text, encoding='utf-8')
                touched += 1
    if touched:
        action = "would update" if dry_run else "updated"
        print(f"  HTML refs {action}: {touched} file(s)")
    return touched


def emit_inplace_jpeg(survey_name, targets, dry_run):
    """Replace each PNG with same-stem JPEG, rewrite HTML refs. JPEG inputs left as-is."""
    docs_dir = SURVEYS_DIR / survey_name / 'docs'
    replacements = []
    total_saved = 0

    for path in targets:
        if path.suffix.lower() != '.png':
            continue  # JPEG inputs already compressed; skip
        original_size = path.stat().st_size
        jpg_out = path.with_suffix('.jpg')

        if dry_run:
            print(f"  [dry] {path.name} ({human(original_size)}) → "
                  f"{jpg_out.name} + remove PNG")
            replacements.append((path.name, jpg_out.name))
            continue

        with Image.open(path) as img:
            flat = flatten_to_rgb(img)
            flat.save(jpg_out, 'JPEG', quality=JPEG_QUALITY, optimize=True)
        new_size = jpg_out.stat().st_size
        path.unlink()
        replacements.append((path.name, jpg_out.name))
        total_saved += max(original_size - new_size, 0)
        print(f"  {path.name} ({human(original_size)}) → "
              f"{jpg_out.name} ({human(new_size)})")

    rewrite_html_refs(docs_dir, replacements, dry_run)
    return total_saved


def process_survey(survey_name, dry_run, inplace_jpeg):
    survey_dir = SURVEYS_DIR / survey_name
    if not survey_dir.is_dir():
        print(f"  SKIP: {survey_name} (no survey dir)")
        return
    targets = list_target_figures(survey_name)
    if not targets:
        print(f"[{survey_name}] no figures over {human(SIZE_THRESHOLD)} — skip")
        return
    total_before = sum(t.stat().st_size for t in targets)
    print(f"[{survey_name}] {len(targets)} target(s), "
          f"total {human(total_before)}")

    if inplace_jpeg:
        saved = emit_inplace_jpeg(survey_name, targets, dry_run)
    else:
        saved = sum(emit_alongside(t, dry_run) for t in targets)

    if not dry_run:
        print(f"[{survey_name}] approx saved: {human(saved)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('survey', nargs='?', help='survey slug (e.g. microbiome-cosmetics-ai)')
    parser.add_argument('--all', action='store_true', help='process every survey')
    parser.add_argument('--dry-run', action='store_true',
                        help='list intended changes without writing')
    parser.add_argument('--inplace-jpeg', action='store_true',
                        help='replace PNG with JPEG and rewrite HTML refs')
    args = parser.parse_args()

    if not args.all and not args.survey:
        parser.error("provide a survey slug or --all")
    if args.all and args.survey:
        parser.error("--all and a survey slug are mutually exclusive")

    if args.all:
        surveys = sorted(p.name for p in SURVEYS_DIR.iterdir()
                         if p.is_dir() and not p.name.startswith('.'))
    else:
        surveys = [args.survey]

    for s in surveys:
        process_survey(s, args.dry_run, args.inplace_jpeg)


if __name__ == '__main__':
    main()
