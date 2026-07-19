# terry-surveys

Public framework and `$survey` skill for Terry's bilingual research survey books.
Survey manuscripts, research artifacts, generated sites, and shared content data
live in the private sibling repository `terryum/terry-surveys-contents`.

## Repository split

| Repository | Visibility | Responsibility |
|---|---|---|
| `terryum/terry-surveys` | Public | skill, harness, schemas, scaffold, builders, shared presentation code |
| `terryum/terry-surveys-contents` | Private | `surveys/<slug>`, assets, bibliography data, glossary masters, maintenance records |

Reader visibility remains independent of GitHub source visibility. A rendered
survey may be public on Cloudflare Pages while its canonical source stays
private.

## Local workspace

Clone both repositories as siblings:

```bash
gh repo clone terryum/terry-surveys
gh repo clone terryum/terry-surveys-contents
cd terry-surveys
bash scripts/setup-contents.sh --check
```

The framework tracks compatibility symlinks for `surveys/`, `assets/`, the
BibTeX data files, and glossary masters. Existing commands therefore keep the
same paths:

```bash
python3 build.py --list
python3 build.py <slug>
python3 build.py --validate --all
python3 build.py --new <slug>
```

`python3 build.py --new <slug>` creates a new folder at
`terry-surveys-contents/surveys/<slug>` through the `surveys` symlink. New
survey metadata points to the private contents repository by default. Public
feedback and contribution reports are centralized in the public
[`terry-surveys` Issues](https://github.com/terryum/terry-surveys/issues).

## Architecture

```text
Codes/personal/
├── terry-surveys/                   # public framework
│   ├── .codex/skills/survey/
│   ├── survey_harness/
│   ├── shared/
│   ├── scripts/
│   ├── surveys -> ../terry-surveys-contents/surveys
│   ├── assets -> ../terry-surveys-contents/assets
│   ├── bibtex/                      # tools + linked master data
│   └── glossary/                    # docs + linked master data
└── terry-surveys-contents/          # private canonical content
    ├── surveys/<slug>/
    ├── assets/
    ├── bibtex/
    ├── glossary/
    └── maintenance/
```

See [CLAUDE.md](CLAUDE.md) for authoring rules and
[source-repositories.md](.codex/skills/survey/references/source-repositories.md)
for the source privacy policy.

## 한국어 요약

`terry-surveys`에는 서베이를 만드는 스킬, 형식, 빌드 도구만 공개로
유지합니다. 실제 S1–S13 콘텐츠와 앞으로 추가될 서베이는 모두 비공개
`terry-surveys-contents/surveys/<slug>` 아래에 저장합니다. 두 저장소를 같은
상위 폴더에 clone하면 기존 `surveys/<slug>` 경로와 빌드 명령을 그대로 쓸
수 있습니다.

## License

MIT for framework code. Survey content retains its own license metadata in the
private contents repository.
