#!/usr/bin/env python3
"""Scaffold a new survey in the linked private contents repository.

Produces the canonical survey structure defined in the root CLAUDE.md
under "서베이 생성 표준". All templates default to the standard layout
so new surveys stay consistent with existing ones.
"""

import os
import json


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _survey_config(name):
    # Home hero uses the canonical title, then subtitle and description.
    # Keep short_title equal to title unless a downstream consumer explicitly
    # supports a separate label. It must never replace the visible book title.
    # description stays short (KO ≤ 90 chars, EN ≤ 140 chars). The long
    # chapter list already renders below as the Chapter Grid, so the
    # description should be a single hook — never a table of contents.
    # See 2026-04 humanoid-revolution incident: description initially
    # listed all four catalysts + all five companies + all three stages,
    # running 243 KO chars / 444 EN chars.
    return {
        "id": name,
        "github_repo": "terryum/terry-surveys-contents",
        # Source repositories are private by default even when the rendered
        # survey is reader-public through Cloudflare/the Terry gallery.
        "github_repo_visibility": "private",
        "title": {
            "ko": "서베이 제목 (한국어)",
            "en": "Survey Title (English)"
        },
        "short_title": {
            "ko": "서베이 제목 (한국어)",
            "en": "Survey Title (English)"
        },
        "subtitle": {
            "ko": "부제목 (한 문장)",
            "en": "Subtitle (one sentence)"
        },
        "description": {
            # KO ≤ 90자, EN ≤ 140 chars. "핵심 질문 한 줄 — N Parts, M Chapters" 패턴.
            "ko": "핵심 질문 한 줄. — N Parts, M Chapters",
            "en": "One-line core question. — N Parts, M Chapters"
        },
        "cover_image": "",  # e.g. "../assets/cover.jpg" (16:9 hero banner above <h1>). Reuse terryum-ai/public/images/projects/survey-<slug>-og.jpg if present.
        "dates": {
            "first_published": "",
            "last_updated": ""
        },
        "features": {
            "glossary": True,
            "pdf": False,
            "paper": False
        },
        "acknowledgment": {
            "ko": [],
            "en": []
        },
        "highlights": {
            "ko": [
                {"icon": "&#x1F4DA;", "title": "하이라이트 1", "desc": "설명을 입력하세요."},
                {"icon": "&#x1F52C;", "title": "하이라이트 2", "desc": "설명을 입력하세요."},
                {"icon": "&#x1F916;", "title": "하이라이트 3", "desc": "설명을 입력하세요."}
            ],
            "en": [
                {"icon": "&#x1F4DA;", "title": "Highlight 1", "desc": "Enter description."},
                {"icon": "&#x1F52C;", "title": "Highlight 2", "desc": "Enter description."},
                {"icon": "&#x1F916;", "title": "Highlight 3", "desc": "Enter description."}
            ]
        },
        "parts": [
            {
                "name": {"ko": "Part I: 파트 제목", "en": "Part I: Part Title"},
                "chapters": [
                    {
                        "num": 1,
                        "title": {"ko": "첫 번째 챕터", "en": "First Chapter"},
                        "summary": {"ko": "요약", "en": "Summary"},
                        "last_updated": ""
                    }
                ]
            }
        ]
    }


def _chapter_template(lang, title):
    heading = "## 1.1 Introduction" if lang == 'en' else "## 1.1 서론"
    refs_heading = "## References" if lang == 'en' else "## 참고문헌"
    return f"""---
chapter: 1
title: "{title}"
part: "Part I"
date: ""
last_updated: ""
---

{heading}

Content goes here.

{refs_heading}

1. Author (Year). Title. *Venue*.
"""


def _glossary_template(lang):
    title = "Glossary" if lang == 'en' else "용어집 (Glossary)"
    # Reader-facing intro ONLY. Maintainer workflow (how to add new terms,
    # how to sync with the master) lives in `glossary/README.md` — NEVER
    # in a published book file. See 2026-04 humanoid-revolution incident:
    # the scaffold blockquote "> **신규 용어 추가 시**: …" rendered as
    # visible instruction text on the public site.
    if lang == 'ko':
        intro = (
            "A~Z 순으로 정리된 주요 용어. 각 항목 끝 `(Ch N)`은 해당 용어가 도입되거나 집중 논의된 챕터."
        )
    else:
        intro = (
            "Key terms in A-Z order. `(Ch N)` marks the chapter where the term is introduced or discussed in depth."
        )
    return f"""---
title: "{title}"
date: ""
last_updated: ""
---

# {title}

{intro}

## A

- **TermA**: Definition (Ch N)

## B

- **TermB**: Definition (Ch N)
"""


def _claude_md(name):
    return f"""# Survey: {name}

## Project Purpose

이 서베이의 목적·대상 독자·범위를 설명하세요.

## Chapter Structure

survey.json의 `parts[].chapters[]`를 따릅니다.

## Harness Pipeline

루트 `CLAUDE.md`의 **정규 에이전트 파이프라인**을 따른다:
`deep-researcher → critical-analyst → book-writer → image-curator → fact-checker → qa-reviewer`

각 단계의 필수 산출물과 포맷은 루트 CLAUDE.md "서베이 생성 표준" 참조.

## Figure Policy

- 논문 원본 figure를 우선으로 한다 (크롭 + 출처 caption).
- AI 보조 일러스트(Gemini 등)는 **챕터당 2개 이하**.
- 파일명: `chNN_<sourceSlug>_fig<N>.<ext>` (flat 구조).

## Build & Deploy

```bash
python3 build.py {name}                          # 로컬 빌드
cd surveys/{name} && bash scripts/push.sh "msg"  # Cloudflare Pages 외부 repo 동기화
```
"""


def _readme(name):
    return f"""# {name}

English | [한국어](#한국어)

> A research survey book in the terry-surveys monorepo.

**Live Website**: (fill in after deploy)

## Overview

Describe the survey purpose, audience, and scope here.

## Structure

- `book/ko/`, `book/en/`: bilingual chapter markdown
- `book/references.bib`: subset of the monorepo master bibliography
- `assets/figures/`: figures (flat, `chNN_<slug>_fig<N>.<ext>`)
- `docs/`: built static site (committed)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions are made through GitHub Issues.

## License

This work is licensed under [CC BY-NC-SA 4.0](LICENSE).

---

## 한국어

terry-surveys 모노레포의 연구 서베이 책입니다.

**라이브 사이트**: (배포 후 기입)

### 개요

서베이 목적, 대상 독자, 범위를 작성하세요.

### 구조

- `book/ko/`, `book/en/`: 한/영 챕터 마크다운
- `book/references.bib`: 모노레포 마스터 참고문헌의 subset
- `assets/figures/`: figure (flat, `chNN_<slug>_fig<N>.<ext>`)
- `docs/`: 빌드된 정적 사이트 (커밋)

### 기여

[CONTRIBUTING.md](CONTRIBUTING.md)을 참고하세요. 모든 기여는 GitHub Issues를 통해 이루어집니다.

### 라이선스

[CC BY-NC-SA 4.0](LICENSE) 라이선스로 배포됩니다.
"""


def _license():
    return """Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International

Copyright (c) 2026 Terry Taewoong Um

This work is licensed under the Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International License.

You are free to:
  - Share: copy and redistribute the material in any medium or format
  - Adapt: remix, transform, and build upon the material

Under the following terms:
  - Attribution: You must give appropriate credit, provide a link to
    the license, and indicate if changes were made.
  - NonCommercial: You may not use the material for commercial purposes.
  - ShareAlike: If you remix, transform, or build upon the material,
    you must distribute your contributions under the same license.

Full license text:
https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode
"""


def _contributing(name):
    return f"""English | 한국어 (below)

# Contributing

Thank you for your interest in improving this book! Contributions from the research community are welcome.

## How to Contribute

This project uses an **issue-based contribution workflow**. Rather than submitting pull requests directly, contributors open GitHub Issues with their suggestions, references, or corrections.

### 1. Suggest New Content
Use the [**Suggest Content**](https://github.com/terryum/terry-surveys/issues/new?template=suggest-content.yml) template to propose new references, figures, or sections.

### 2. Report Errors
Use the [**Error Report**](https://github.com/terryum/terry-surveys/issues/new?template=error-report.yml) template to report typos, factual errors, or broken links.

### 3. Translation Improvements
Use the [**Translation Improvement**](https://github.com/terryum/terry-surveys/issues/new?template=translation-fix.yml) template for Korean/English wording fixes.

## Credit Policy

Accepted content suggestions are credited as Contributors in the README. Error reports and translation improvements are credited in individual commit messages.

## License

By submitting, you agree that your contributions may be used under [CC BY-NC-SA 4.0](LICENSE) with attribution.

---

# 기여 가이드 (한국어)

이 책의 개선에 관심을 가져주셔서 감사합니다. 연구 커뮤니티의 기여를 환영합니다.

## 기여 방법

본 프로젝트는 **이슈 기반 기여 방식**을 사용합니다. Pull Request 대신 GitHub Issue로 제안/수정 사항을 공유해 주시면 저자가 검토 후 반영합니다.

### 1. 콘텐츠 제안
[**Suggest Content**](https://github.com/terryum/terry-surveys/issues/new?template=suggest-content.yml) 템플릿을 사용해 새로운 레퍼런스, figure, 섹션을 제안합니다.

### 2. 오류 신고
[**Error Report**](https://github.com/terryum/terry-surveys/issues/new?template=error-report.yml) 템플릿을 사용해 오탈자, 사실 오류, 깨진 링크 등을 신고합니다.

### 3. 번역 개선
[**Translation Improvement**](https://github.com/terryum/terry-surveys/issues/new?template=translation-fix.yml) 템플릿으로 한/영 번역 개선을 제안합니다.

## 크레딧 정책

반영된 콘텐츠 제안은 README의 Contributors 섹션에 기록됩니다. 오류 신고와 번역 개선은 개별 커밋 메시지에 반영됩니다.

## 라이선스

기여 시 본인의 기여가 [CC BY-NC-SA 4.0](LICENSE) 하에 사용됨에 동의합니다.
"""


def _issue_config(name):
    return f"""blank_issues_enabled: false
contact_links:
  - name: General Discussion
    url: https://github.com/terryum/{name}/discussions
    about: For general questions and discussions about the book
"""


def _issue_suggest_content():
    return """name: Suggest Content
description: Propose new content, references, or materials for the book
title: "[Content] "
labels: ["enhancement"]
assignees: ["terryum"]
body:
  - type: dropdown
    id: type
    attributes:
      label: Content type
      options:
        - "New section in existing chapter"
        - "Additional reference / citation"
        - "New figure / illustration"
        - "Strengthen existing content"
    validations:
      required: true
  - type: input
    id: chapter
    attributes:
      label: Related chapter (e.g., Ch03, Glossary)
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: What content should be added?
      description: Describe the content you'd like to see. Include key points, references, specs, etc.
    validations:
      required: true
  - type: textarea
    id: links
    attributes:
      label: Reference links
      placeholder: |
        - https://arxiv.org/abs/...
        - https://...
    validations:
      required: false
  - type: textarea
    id: rationale
    attributes:
      label: Why is this important?
    validations:
      required: true
  - type: checkboxes
    id: license
    attributes:
      label: License agreement
      options:
        - label: I agree that submitted materials may be used under CC BY-NC-SA 4.0 with attribution.
          required: true
"""


def _issue_error_report():
    return """name: Report Error
description: Found a typo, factual error, or broken link in the book?
title: "[Error] "
labels: ["error"]
assignees: ["terryum"]
body:
  - type: input
    id: chapter
    attributes:
      label: Chapter (e.g., Ch03, Glossary)
    validations:
      required: true
  - type: dropdown
    id: language
    attributes:
      label: Language version
      options:
        - "Korean (book/ko/)"
        - "English (book/en/)"
        - "Both"
    validations:
      required: true
  - type: textarea
    id: location
    attributes:
      label: Location
      description: Section heading, line number, or quote the problematic text.
    validations:
      required: true
  - type: textarea
    id: description
    attributes:
      label: What's wrong?
    validations:
      required: true
  - type: textarea
    id: suggestion
    attributes:
      label: Suggested correction (optional)
    validations:
      required: false
"""


def _issue_translation_fix():
    return """name: Translation Improvement
description: Suggest a better Korean or English translation
title: "[Translation] "
labels: ["translation"]
assignees: ["terryum"]
body:
  - type: dropdown
    id: direction
    attributes:
      label: Which version to improve?
      options:
        - "Korean version (book/ko/)"
        - "English version (book/en/)"
    validations:
      required: true
  - type: input
    id: chapter
    attributes:
      label: Chapter (e.g., Ch03, Glossary)
    validations:
      required: true
  - type: textarea
    id: current
    attributes:
      label: Current text
    validations:
      required: true
  - type: textarea
    id: suggested
    attributes:
      label: Suggested translation
    validations:
      required: true
  - type: textarea
    id: reason
    attributes:
      label: Why is this better?
    validations:
      required: true
"""


def _push_script(name):
    return f"""#!/usr/bin/env bash
# Deploy this survey's docs/ to Cloudflare Pages via wrangler direct upload.
#
# Cloudflare Pages project: {name}
# (configured with Git Provider: No — direct upload only)
#
# Usage:
#   bash scripts/push.sh [commit message]
#
# The survey's docs/ is built by `python3 build.py {name}` from the
# monorepo root. This script assumes docs/ is already up to date.
#
# Never uploads revise-source/ (local-only source material — gitignored
# and explicitly excluded here to keep the Cloudflare deploy bundle clean).

set -euo pipefail

PROJECT_NAME="{name}"
SRC_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)/docs"
MSG="${{1:-update $PROJECT_NAME}}"

if [ ! -d "$SRC_DIR" ]; then
  echo "ERROR: $SRC_DIR not found. Run 'python3 build.py {name}' first." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d -t pages-deploy-XXXX)"
trap "rm -rf '$TMP_DIR'" EXIT

echo "=== rsync docs/ → $TMP_DIR (excluding revise-source/) ==="
rsync -a \\
  --exclude='revise-source' \\
  --exclude='revise-source/**' \\
  --exclude='.DS_Store' \\
  "$SRC_DIR/" "$TMP_DIR/"

echo "=== wrangler pages deploy ==="
npx wrangler pages deploy "$TMP_DIR" \\
  --project-name="$PROJECT_NAME" \\
  --commit-message="$MSG" \\
  --commit-dirty=true

echo "Done. Live at https://${{PROJECT_NAME}}.pages.dev/"
"""


def _gitignore():
    return """.DS_Store
.wrangler/
_workspace/
revise-source/
docs/revise-source/
_revise-source/
assets/
docs/
*.pdf
*.mp3
*.mp4
*.zip
*.tmp
"""


def create_survey(name, surveys_dir):
    """Create a new survey directory with template files following the canonical structure."""
    survey_dir = os.path.join(surveys_dir, name)
    if os.path.exists(survey_dir):
        print(f"ERROR: surveys/{name}/ already exists")
        return

    print(f"Creating new survey: {name}")

    for d in [
        'book/ko', 'book/en',
        'assets/figures',
        'docs',
        'scripts',
        '.claude/agents',
    ]:
        os.makedirs(os.path.join(survey_dir, d), exist_ok=True)

    with open(os.path.join(survey_dir, 'survey.json'), 'w', encoding='utf-8') as f:
        json.dump(_survey_config(name), f, ensure_ascii=False, indent=2)

    for lang, title in [('ko', '첫 번째 챕터'), ('en', 'First Chapter')]:
        _write(os.path.join(survey_dir, 'book', lang, 'ch01.md'),
               _chapter_template(lang, title))
        _write(os.path.join(survey_dir, 'book', lang, 'glossary.md'),
               _glossary_template(lang))

    _write(os.path.join(survey_dir, 'book', 'references.bib'),
           '% BibTeX references — subset of the private contents master\n')

    _write(os.path.join(survey_dir, 'CLAUDE.md'), _claude_md(name))
    _write(os.path.join(survey_dir, 'README.md'), _readme(name))
    _write(os.path.join(survey_dir, 'LICENSE'), _license())
    _write(os.path.join(survey_dir, 'CONTRIBUTING.md'), _contributing(name))
    _write(os.path.join(survey_dir, '.gitignore'), _gitignore())

    push_path = os.path.join(survey_dir, 'scripts', 'push.sh')
    _write(push_path, _push_script(name))
    os.chmod(push_path, 0o755)

    print(f"\nCreated survey at surveys/{name}/")
    print("Next steps:")
    print(f"  1. Edit surveys/{name}/survey.json with your chapter structure")
    print(f"  2. Populate .claude/agents/ via /survey bootstrap flow")
    print(f"     (scaffold creates the empty dir; agent template is copied by /survey)")
    print(f"  3. Write chapters in surveys/{name}/book/ko/ and book/en/")
    print(f"  4. Fill book/{{ko,en}}/glossary.md with domain terms")
    print(f"  5. Run: python3 build.py {name}")
