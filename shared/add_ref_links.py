#!/usr/bin/env python3
"""Add [scholar] links to all references and fix known issues across all surveys.

Usage:
    python3 shared/add_ref_links.py [survey-name|--all]
"""

import re
import os
import sys
from urllib.parse import quote_plus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')

# Post slug mapping: keyword -> slug
POST_SLUGS = {
    'mano': '2201-mano-hand-model',
    'diffusion policy': '2303-diffusion-policy',
    'umi': '2402-umi-universal-manipulation-interface',
    'stretchable glove': '2407-stretchable-glove-hand-pose',
    'tactile skin': '2407-tactile-skin-inhand-translation',
    '3dtactile': '2409-3dtactile-dex',
    'pi0': '2410-pi0-vla-flow-model',
    'dexforce': '2501-dexforce-force-informed-actions',
    'pp-tac': '2504-pp-tac',
    'dexumi': '2505-dexumi',
    'forcevla': '2505-forcevla-force-aware-moe',
    'exostart': '2506-exostart',
    'dexop': '2509-dexop',
    'act-1': '2511-act1-robot-foundation-model',
    'equitac': '2511-equitac-tactile-equivariance',
    'gen-0': '2511-gen0-embodied-foundation-model',
    'pi0.5': '2511-pi0-6-recap',
    'recap': '2511-pi0-6-recap',
    'osmo': '2512-osmo-tactile-glove',
    'unitachand': '2512-unitachand',
    'umi-ft': '2601-umi-ft-compliant-manipulation',
    'habilis': '2602-habilis-vla-on-device',
    'egoscale': '2602-humanplus-humanoid-shadowing',
    'robopaint': '2602-robopaint',
    'cap-x': '2603-capx-coding-agents-manipulation',
    'roboclaw': '2603-roboclaw-agentic-long-horizon',
    'gen-1': '2604-gen1-scaling-mastery',
    'self-driving lab': '2604-self-driving-labs',
}

# Known fixes: (survey, chapter, ref_num) -> fix_type
FIXES = {
    # SNU survey fixes
    ('snu-tactile-hand', '01', 'arxiv_placeholder'): ('2505.xxxxx', '2509.04441'),
    ('snu-tactile-hand', '04', 'slug_fix_8'): ('2501-umi', '2402-umi-universal-manipulation-interface'),
    ('snu-tactile-hand', '04', 'slug_fix_9'): ('2503-act1-humanoid-hand', '2511-act1-robot-foundation-model'),
    ('snu-tactile-hand', '02', 'remove_post_15'): 'umi-on-legs-force-touch',
    ('snu-tactile-hand', '08', 'remove_post_21'): 'umi-on-legs',
    ('snu-tactile-hand', '11', 'slug_fix_10'): ('2506-umi-on-legs', '2601-umi-ft-compliant-manipulation'),
}


def extract_title_from_ref(ref_text):
    """Extract paper title from a reference line."""
    # Pattern 1: Author, "Title," venue (VLA survey format)
    m = re.search(r'"(.+?)"', ref_text)
    if m:
        return m.group(1).strip().rstrip('.').rstrip(',')

    # Pattern 2: Author (Year). Title. *Venue*.
    m = re.search(r'\(\d{4}\)\.\s*(.+?)(?:\.\s*\*|\.\s*(?:arXiv|IEEE|ICRA|IROS|CoRL|NeurIPS|ICML|CVPR|ICLR|RSS|Sensors|Nature|Science|PNAS|RA-L|T-RO)|\.\s*http|\.\s*\[)', ref_text)
    if m:
        return m.group(1).strip().rstrip('.')

    # Pattern 3: Author, Year. Title. after comma+year
    m = re.search(r',\s*\d{4}\.\s*$', ref_text)

    # Fallback: try after year
    m = re.search(r'\(\d{4}\)\.\s*(.+?)(?:\.\s|$)', ref_text)
    if m:
        title = m.group(1).strip().rstrip('.')
        if len(title) < 200:
            return title

    # Fallback 2: after year for comma format (Author et al., "Title," venue, year.)
    m = re.search(r'(?:,\s*|\.\s*)"?(.+?)"?(?:,\s*arXiv|\.\s*$)', ref_text)
    if m:
        title = m.group(1).strip().strip('"').rstrip('.')
        if len(title) < 200 and len(title) > 5:
            return title

    return ''


def make_scholar_link(title):
    """Create Google Scholar search link."""
    if not title:
        return ''
    # Clean title
    clean = re.sub(r'[*_`]', '', title).strip()
    clean = re.sub(r'\s+', '+', clean)
    # URL encode special chars but keep +
    encoded = quote_plus(clean).replace('%2B', '+')
    return f'[scholar](https://scholar.google.com/scholar?q={encoded})'


def has_scholar_link(line):
    """Check if line already has a [scholar] link."""
    return '[scholar]' in line


def has_post_link(line):
    """Check if line already has a [post] link."""
    return '[post]' in line


def find_post_slug(ref_text):
    """Try to match a reference to a known post slug."""
    text_lower = ref_text.lower()
    for keyword, slug in POST_SLUGS.items():
        if keyword in text_lower:
            return slug
    return None


def process_ref_line(line, lang_code):
    """Process a single reference line, adding missing links."""
    if not re.match(r'^\d+\.', line.strip()):
        return line

    modified = line.rstrip()

    # Add [scholar] if missing
    if not has_scholar_link(modified):
        title = extract_title_from_ref(modified)
        if title:
            scholar = make_scholar_link(title)
            if scholar:
                modified = modified + ' ' + scholar

    return modified + '\n' if line.endswith('\n') else modified


def apply_fixes(content, survey_id, ch_num, lang_code):
    """Apply known fixes to file content."""
    if survey_id == 'snu-tactile-hand':
        if ch_num == '01':
            content = content.replace('2505.xxxxx', '2509.04441')
        if ch_num == '04':
            # Fix UMI slug
            content = re.sub(
                r'\[#\d+\]\(https://terry\.artlab\.ai/\w+/posts/2501-umi[^)]*\)',
                lambda m: m.group(0).replace('2501-umi-universal-manipulation-interface', '2402-umi-universal-manipulation-interface').replace('2501-umi-', '2402-umi-universal-manipulation-interface') if '2501-umi' in m.group(0) else m.group(0),
                content
            )
            # Fix ACT-1 slug
            content = content.replace('2503-act1-humanoid-hand', '2511-act1-robot-foundation-model')
        if ch_num == '02':
            # Remove broken UMI on Legs post link
            content = re.sub(r'\s*\[#\d+\]\(https://terry\.artlab\.ai/\w+/posts/2502-umi-on-legs[^)]*\)', '', content)
        if ch_num == '08':
            # Remove broken UMI on Legs post link
            content = re.sub(r'\s*\[#\d+\]\(https://terry\.artlab\.ai/\w+/posts/2410-umi-on-legs[^)]*\)', '', content)
        if ch_num == '11':
            # Fix UMI-FT slug
            content = content.replace('2506-umi-on-legs', '2601-umi-ft-compliant-manipulation')

    if survey_id == 'robot-hand-tactile-sensor':
        if ch_num == '04':
            content = content.replace('arXiv:2602.xxxxx', 'arXiv:2603.12120')
            content = content.replace('2602.xxxxx', '2603.12120')
        if ch_num == '06':
            # Fix duplicated venue text
            content = content.replace('*Sensors*. *Sensors*.', '*Sensors*.')
            content = content.replace('*arXiv preprint*. *arXiv preprint*.', '*arXiv preprint*.')
            # Fix placeholder arXiv
            content = content.replace('arXiv:2404.xxxxx', 'arXiv:2212.04498')
            content = content.replace('2404.xxxxx', '2212.04498')
        if ch_num == '07':
            content = content.replace('arXiv:2407.xxxxx', 'arXiv:2407.07885')
            content = content.replace('2407.xxxxx', '2407.07885')
        if ch_num == '10':
            content = content.replace('arXiv:2404.xxxxx', 'arXiv:2212.04498')
            content = content.replace('2404.xxxxx', '2212.04498')

    if survey_id == 'vla-agentic-robotics':
        # Fix hallucinated/incorrect titles
        content = content.replace(
            'Benchmarking Coding Agents for Robot Manipulation',
            'A Framework for Benchmarking and Improving Coding Agents for Robot Manipulation'
        )
        content = content.replace(
            '"CaP-X: Benchmarking Coding Agents',
            '"CaP-X: A Framework for Benchmarking and Improving Coding Agents'
        )
        content = content.replace(
            'Leveraging Code Generation for Task and Motion Planning',
            'Foundation Model-Based Robot Planning via Symbolic Code Generation'
        )
        content = content.replace(
            '"Code-as-Symbolic-Planner: Leveraging Code Generation',
            '"Foundation Model-Based Robot Planning via Symbolic Code Generation'
        )
        content = content.replace(
            'Learning to Plan and Act by Experiencing in the Real World',
            'A Pragmatist Robot: Learning to Plan Tasks by Experiencing the Real World'
        )
        content = content.replace(
            'A Multi-memory Agentic Framework for Lifelong Robot Learning',
            'A Brain-inspired Multi-memory Agentic Framework for Interactive Environmental Learning in Physical Embodied Systems'
        )
        # Fix ch09 ref 8 hallucination
        content = content.replace(
            'Tian, S. et al., "Bridging the Sim2Real Gap with CLIP-based Pre-trained Vision Encoders for Robot Manipulation',
            'Yardi, Y. et al., "Bridging the Sim2Real Gap: Vision Encoder Pre-Training for Visuomotor Policy Transfer'
        )

    return content


def process_survey(survey_id):
    """Process all chapters in a survey."""
    survey_dir = os.path.join(SURVEYS_DIR, survey_id)
    if not os.path.isdir(survey_dir):
        print(f"ERROR: Survey not found: {survey_id}")
        return

    stats = {'files': 0, 'refs_processed': 0, 'scholar_added': 0, 'fixes_applied': 0}

    for lang in ['ko', 'en']:
        book_dir = os.path.join(survey_dir, 'book', lang)
        if not os.path.isdir(book_dir):
            continue
        lang_code = lang

        for fname in sorted(os.listdir(book_dir)):
            if not fname.startswith('ch') or not fname.endswith('.md'):
                continue
            ch_num = fname.replace('ch', '').replace('.md', '')
            fpath = os.path.join(book_dir, fname)

            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()

            original = content

            # Apply known fixes
            content = apply_fixes(content, survey_id, ch_num, lang_code)

            # Find reference section
            ref_start = -1
            for marker in ['## 참고문헌', '## References']:
                idx = content.find(marker)
                if idx != -1:
                    ref_start = idx
                    break

            if ref_start == -1:
                continue

            # Split into before-refs and refs
            before_refs = content[:ref_start]
            refs_section = content[ref_start:]

            # Process each reference line
            lines = refs_section.split('\n')
            new_lines = []
            for line in lines:
                if re.match(r'^\d+\.\s+', line.strip()):
                    stats['refs_processed'] += 1
                    if not has_scholar_link(line):
                        title = extract_title_from_ref(line)
                        if title:
                            scholar = make_scholar_link(title)
                            if scholar:
                                line = line.rstrip() + ' ' + scholar
                                stats['scholar_added'] += 1
                new_lines.append(line)

            new_content = before_refs + '\n'.join(new_lines)

            if new_content != original:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                stats['files'] += 1
                if content != original:  # fixes were applied
                    stats['fixes_applied'] += 1
                print(f"  Updated: {lang}/{fname}")

    print(f"\n  {survey_id} stats:")
    print(f"    Files modified: {stats['files']}")
    print(f"    Refs processed: {stats['refs_processed']}")
    print(f"    [scholar] added: {stats['scholar_added']}")
    print(f"    Fixes applied: {stats['fixes_applied']}")
    return stats


def main():
    if len(sys.argv) < 2 or sys.argv[1] == '--all':
        surveys = []
        for name in sorted(os.listdir(SURVEYS_DIR)):
            if os.path.isfile(os.path.join(SURVEYS_DIR, name, 'survey.json')):
                surveys.append(name)
    else:
        surveys = [sys.argv[1]]

    total_stats = {'files': 0, 'refs_processed': 0, 'scholar_added': 0, 'fixes_applied': 0}

    for survey in surveys:
        print(f"\nProcessing: {survey}")
        print('=' * 50)
        stats = process_survey(survey)
        if stats:
            for k in total_stats:
                total_stats[k] += stats[k]

    print(f"\n{'=' * 50}")
    print(f"TOTAL: {total_stats['files']} files, {total_stats['refs_processed']} refs, "
          f"{total_stats['scholar_added']} [scholar] added, {total_stats['fixes_applied']} fixes")


if __name__ == '__main__':
    main()
