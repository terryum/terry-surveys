# terry-surveys — Research Survey Book Workspace

[한국어](#한국어) | **English**

> Unified workspace for creating, building, and managing research survey books on [terry.artlab.ai](https://terry.artlab.ai/ko/surveys).

This workspace is part of the [terryum-ai](https://github.com/terryum/terryum-ai) ecosystem. For full site documentation, architecture, and setup guide, see the [main repository README](https://github.com/terryum/terryum-ai#readme).

---

## What This Does

This workspace manages **survey book creation** — multi-chapter bilingual (KO/EN) research survey books built from academic papers. Each survey is a standalone static site deployed on Vercel, embedded in the homepage's Surveys gallery.

### Current Surveys

| # | Title | Papers | Status |
|---|-------|--------|--------|
| S1 | Robot Hand & Tactile Sensor | 131+ | Active |
| S3 | Korean VLA & Agentic Robotics | 146+ | Active |
| S2 | SNU Large-Scale Tactile Hand | — | Group-restricted (SNU) |

### Key Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `python3 build.py <name>` | Build a survey site | `python3 build.py vla-agentic-robotics` |
| `python3 build.py --all` | Build all surveys | |
| `python3 build.py --new <name>` | Scaffold a new survey | `python3 build.py --new my-survey` |
| `/survey` | Register survey in homepage gallery | `/survey https://survey-name.vercel.app` |

## Architecture

```
terry-surveys/
├── build.py               # CLI orchestrator
├── shared/                # Shared build infrastructure
│   ├── build_site.py      # Markdown → HTML converter
│   ├── scaffold.py        # New survey template generator
│   ├── css/style.css      # Shared stylesheet
│   └── js/                # Shared JavaScript
└── surveys/               # Individual survey projects
    ├── vla-agentic-robotics/
    ├── robot-hand-tactile-sensor/
    └── snu-tactile-hand/    # Group-restricted
```

Each survey contains:
```
surveys/<name>/
├── survey.json            # Metadata (bilingual titles, chapters, etc.)
├── book/ko/ + book/en/    # Markdown chapters
├── assets/figures/        # Images
├── docs/                  # Build output (deployed to Vercel)
└── vercel.json            # Deployment config
```

## Creating a New Survey

```bash
# 1. Scaffold
python3 build.py --new my-new-survey

# 2. Write chapters in surveys/my-new-survey/book/ko/ and book/en/

# 3. Build
python3 build.py my-new-survey

# 4. Deploy (commit docs/ → Vercel auto-deploys)
cd surveys/my-new-survey && git add docs/ && git commit -m "build" && git push

# 5. Register in homepage gallery
/survey https://my-new-survey.vercel.app
```

## Group-Restricted Surveys

Surveys can be restricted to specific groups (e.g., SNU collaborators):
- Content directories are listed in `.gitignore` (never pushed to public repo)
- Registered in Supabase `private_content` table with `group_slug`
- Visible only after `/co/snu` login on the homepage

---

# 한국어

# terry-surveys — 연구 서베이 북 워크스페이스

> [terry.artlab.ai](https://terry.artlab.ai/ko/surveys)의 연구 서베이 북을 생성·빌드·관리하는 통합 워크스페이스.

이 워크스페이스는 [terryum-ai](https://github.com/terryum/terryum-ai) 생태계의 일부입니다. 전체 사이트 문서, 아키텍처, 설정 가이드는 [메인 리포지토리 README](https://github.com/terryum/terryum-ai#readme)를 참고하세요.

## 하는 일

학술 논문을 바탕으로 다챕터 양국어(한/영) 연구 서베이 북을 제작합니다. 각 서베이는 독립적인 정적 사이트로 Vercel에 배포되며, 홈페이지의 Surveys 갤러리에 임베딩됩니다.

### 주요 명령어

| 명령어 | 기능 | 예시 |
|--------|------|------|
| `python3 build.py <이름>` | 서베이 사이트 빌드 | `python3 build.py vla-agentic-robotics` |
| `python3 build.py --new <이름>` | 새 서베이 스캐폴드 | `python3 build.py --new my-survey` |
| `/survey` | 홈페이지 갤러리에 등록 | `/survey https://survey-name.vercel.app` |

## 새 서베이 만들기

```bash
# 1. 스캐폴드
python3 build.py --new my-new-survey

# 2. surveys/my-new-survey/book/ko/ 와 book/en/ 에 챕터 작성

# 3. 빌드
python3 build.py my-new-survey

# 4. 배포 (docs/ 커밋 → Vercel 자동 배포)

# 5. 홈페이지 갤러리 등록
/survey https://my-new-survey.vercel.app
```

## License

MIT
