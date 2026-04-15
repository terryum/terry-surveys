#!/usr/bin/env python3
"""Scaffold a new survey project in the monorepo."""

import os
import json


def create_survey(name, surveys_dir):
    """Create a new survey directory with template files."""
    survey_dir = os.path.join(surveys_dir, name)
    if os.path.exists(survey_dir):
        print(f"ERROR: surveys/{name}/ already exists")
        return

    print(f"Creating new survey: {name}")

    # Create directories
    for d in [
        'book/ko', 'book/en',
        'assets/figures',
        'docs',
    ]:
        os.makedirs(os.path.join(survey_dir, d), exist_ok=True)

    # survey.json template
    config = {
        "id": name,
        "github_repo": f"terryum/{name}",
        "title": {
            "ko": "서베이 제목 (한국어)",
            "en": "Survey Title (English)"
        },
        "short_title": {
            "ko": "짧은 제목",
            "en": "Short Title"
        },
        "subtitle": {
            "ko": "부제목",
            "en": "Subtitle"
        },
        "description": {
            "ko": "설명",
            "en": "Description"
        },
        "dates": {
            "first_published": "",
            "last_updated": ""
        },
        "features": {
            "glossary": False,
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
                        "summary": {"ko": "요약", "en": "Summary"}
                    }
                ]
            }
        ]
    }

    with open(os.path.join(survey_dir, 'survey.json'), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Template chapter files
    for lang, title in [('ko', '첫 번째 챕터'), ('en', 'First Chapter')]:
        ch_content = f'''---
chapter: 1
title: "{title}"
part: "Part I"
date: ""
last_updated: ""
---

## 1.1 Introduction

Content goes here.

## References

1. Author (Year). Title. *Venue*.
'''
        with open(os.path.join(survey_dir, 'book', lang, 'ch01.md'), 'w', encoding='utf-8') as f:
            f.write(ch_content)

    # Empty references.bib
    with open(os.path.join(survey_dir, 'book', 'references.bib'), 'w', encoding='utf-8') as f:
        f.write('% BibTeX references\n')

    # vercel.json
    vercel = {
        "outputDirectory": "docs",
        "buildCommand": None,
        "installCommand": None,
        "framework": None,
        "redirects": [
            {"source": "/ch:num(\\d+).html", "destination": "/ko/ch:num.html", "statusCode": 302},
            {"source": "/references.html", "destination": "/ko/references.html", "statusCode": 302}
        ]
    }
    with open(os.path.join(survey_dir, 'vercel.json'), 'w', encoding='utf-8') as f:
        json.dump(vercel, f, indent=2)

    # CLAUDE.md template
    claude_md = f'''# Survey: {name}

## Project Purpose

이 서베이의 목적을 설명하세요.

## Chapter Structure

survey.json을 참조하세요.

## Work Principles

- 수치 기반: 모든 claim에 출처 논문과 구체적 수치를 명시
- 비판적 시각: 각 접근의 한계와 미해결 문제를 명확히 지적
- 양국어: 한글(ko) 원고가 주, 영문(en)은 동시 생성
'''
    with open(os.path.join(survey_dir, 'CLAUDE.md'), 'w', encoding='utf-8') as f:
        f.write(claude_md)

    print(f"\nCreated survey at surveys/{name}/")
    print("Next steps:")
    print(f"  1. Edit surveys/{name}/survey.json with your chapter structure")
    print(f"  2. Write chapters in surveys/{name}/book/ko/ and book/en/")
    print(f"  3. Run: python build.py {name}")
