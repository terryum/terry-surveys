# Glossary Master — terry-surveys 공통 용어집

`bibtex/references.bib`가 참고문헌의 single source of truth인 것처럼, 이 디렉토리의 `master_ko.md` / `master_en.md`는 **모든 서베이가 공유하는 용어집 마스터**다. 각 서베이의 `book/<lang>/glossary.md`는 이 마스터의 subset으로 유지한다.

## 왜 마스터인가

- 여러 서베이에서 같은 용어(예: `VLA`, `Cross-embodiment gap`, `Diffusion Policy`)가 등장할 때 **정의가 제각각**이 되면 독자가 혼란스럽다.
- 마스터에서 canonical 정의를 관리하면 서베이 간 용어 일관성이 보장된다.
- 신규 서베이 작성 시 마스터에서 관련 항목을 복사해 subset을 빠르게 구성할 수 있다.

## 워크플로우 (필수)

신규 용어를 서베이 glossary에 추가할 때 다음 4단계를 따른다.

1. **마스터 grep 먼저**:
   ```bash
   grep -i "^- \*\*<term>" glossary/master_ko.md
   ```
2. **있으면 정의 재사용**: 마스터의 한 줄 전체를 서베이 `book/<lang>/glossary.md`의 해당 알파벳 섹션에 복사. 서베이별로 필요한 `(Ch N)` 챕터 참조만 뒤에 추가.
3. **없으면 마스터에 먼저 추가**: `master_ko.md`와 `master_en.md` 양쪽에 canonical 정의를 먼저 넣고, 그 후 서베이 subset으로 복사.
4. **자매 서베이 확인**: 이미 다른 서베이에 해당 용어가 있다면 정의 불일치 여부 점검 — 불일치하면 마스터 기준으로 정렬.

## 자동 동기화: `--sync-glossary`

마스터만 수정하면 나머지는 자동화 가능:

```bash
# 마스터 1회 수정 후 모든 서베이를 마스터 subset으로 재생성
python3 build.py --sync-glossary robot-hand-tactile-sensor
python3 build.py --sync-glossary snu-tactile-hand
python3 build.py --sync-glossary vla-agentic-robotics
```

동작:
- 마스터의 모든 용어에 대해, 서베이 챕터 본문(ko/en 각각)을 스캔해 해당 용어가 ≥1회 등장하는지 확인.
- 등장한 용어만 서베이 `book/<lang>/glossary.md`에 마스터 정의 그대로 복사 + `(Ch N, Ch M)` 챕터 참조 자동 부기.
- 서베이 로컬 glossary의 frontmatter와 intro 문장은 그대로 유지, A-Z 섹션만 재생성.
- 결과적으로 서베이 glossary는 항상 마스터의 일관된 subset.

정의 drift 검증은 `python3 build.py --validate <name>`가 수행 — 서베이 로컬 정의가 마스터와 cosmetic 차이를 넘어 갈라지면 warning.

## 엔트리 포맷

```markdown
- **Term Name (약어/별칭)**: 한 문장 canonical 정의. 필요 시 핵심 저자·연도·출처를 붙인다.
```

- 마스터에는 `(Ch N)` 같은 **챕터 참조를 넣지 않는다** (서베이마다 챕터가 다르므로).
- 서베이 glossary에 복사할 때만 해당 서베이의 챕터 번호를 `(Ch N)`으로 부기.
- 알파벳 대문자 1개 섹션 (`## A`, `## B`, ...) 으로 묶고, 각 섹션 안에서 용어는 알파벳 순.

## 빌드와의 관계

- `shared/build_site.py`의 `build_glossary_html()`은 각 서베이의 `book/<lang>/glossary.md`만 읽는다 (마스터를 직접 읽지 않음).
- 서베이 `features.glossary=true`일 때만 glossary 페이지와 네비 링크가 생성된다 (기본값 true).
- 챕터 페이지 하단 네비와 TOC 인덱스 부록(Appendix)에서 glossary 페이지로 링크한다.

## 새 서베이 만들 때

`python3 build.py --new <name>` 실행 시 `shared/scaffold.py`가 빈 glossary 템플릿을 생성한다. 거기서부터 **마스터 grep → 관련 용어 복사 → 챕터 참조 추가** 순으로 채우면 된다.
