#!/usr/bin/env python3
"""terry-surveys monorepo build CLI.

Usage:
    python build.py <survey-name>          # Build a single survey
    python build.py --all                  # Build all surveys
    python build.py --new <survey-name>    # Scaffold a new survey
    python build.py --list                 # List available surveys
    python build.py --index                # Rebuild refs_index.json
    python build.py --match <post-slug>    # Find survey refs matching a post
    python build.py --search <keyword>     # Search refs by keyword
    python build.py --validate [name|--all]        # Structural validator
    python build.py --sync-bibtex <name>           # Regenerate local .bib from master
    python build.py --sync-glossary <name>         # Regenerate local glossary from master
    python build.py --staleness [name|--all]       # Chapter staleness report
"""

import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
SHARED_DIR = os.path.join(ROOT, 'shared')

# Add shared to path so we can import build_site
sys.path.insert(0, ROOT)


def list_surveys():
    """List all available survey directories."""
    surveys = []
    if os.path.exists(SURVEYS_DIR):
        for name in sorted(os.listdir(SURVEYS_DIR)):
            config_path = os.path.join(SURVEYS_DIR, name, 'survey.json')
            if os.path.isfile(config_path):
                surveys.append(name)
    return surveys


def build_one(name):
    """Build a single survey by name."""
    survey_dir = os.path.join(SURVEYS_DIR, name)
    config_path = os.path.join(survey_dir, 'survey.json')

    if not os.path.isfile(config_path):
        print(f"ERROR: survey.json not found in surveys/{name}/")
        sys.exit(1)

    from shared.build_site import build_survey, load_config
    config, _, _, _ = load_config(survey_dir)

    print(f"\n{'='*60}")
    print(f"Building: {config['title']['en']}")
    print(f"{'='*60}\n")

    build_survey(config, survey_dir, SHARED_DIR)


def scaffold_new(name):
    """Create a new survey from template."""
    from shared.scaffold import create_survey
    create_survey(name, SURVEYS_DIR)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        surveys = list_surveys()
        if surveys:
            print("Available surveys:")
            for s in surveys:
                print(f"  - {s}")
        sys.exit(0)

    arg = sys.argv[1]

    if arg == '--list':
        for s in list_surveys():
            print(s)

    elif arg == '--all':
        surveys = list_surveys()
        if not surveys:
            print("No surveys found in surveys/")
            sys.exit(1)
        for name in surveys:
            build_one(name)
        print(f"\nAll {len(surveys)} surveys built successfully!")

    elif arg == '--new':
        if len(sys.argv) < 3:
            print("Usage: python build.py --new <survey-name>")
            sys.exit(1)
        scaffold_new(sys.argv[2])

    elif arg == '--index':
        from bibtex.refs_index import build_index
        build_index()

    elif arg == '--match':
        if len(sys.argv) < 3:
            print("Usage: python build.py --match <post-slug>")
            sys.exit(1)
        from bibtex.refs_index import match_post_slug
        match_post_slug(sys.argv[2])

    elif arg == '--search':
        if len(sys.argv) < 3:
            print("Usage: python build.py --search <keyword>")
            sys.exit(1)
        from bibtex.refs_index import search_index
        search_index(sys.argv[2])

    elif arg == '--validate':
        from shared.validate import main as validate_main
        target = sys.argv[2] if len(sys.argv) >= 3 else '--all'
        validate_main(target)

    elif arg == '--sync-bibtex':
        if len(sys.argv) < 3:
            print("Usage: python build.py --sync-bibtex <survey-name>")
            sys.exit(1)
        from shared.sync_master import sync_bibtex
        sync_bibtex(sys.argv[2])

    elif arg == '--sync-glossary':
        if len(sys.argv) < 3:
            print("Usage: python build.py --sync-glossary <survey-name>")
            sys.exit(1)
        from shared.sync_master import sync_glossary
        sync_glossary(sys.argv[2])

    elif arg == '--staleness':
        from shared.staleness import main as staleness_main
        target = sys.argv[2] if len(sys.argv) >= 3 else '--all'
        staleness_main(target)

    else:
        build_one(arg)


if __name__ == '__main__':
    main()
