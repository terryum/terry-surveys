---
name: link-post-to-surveys
description: "새 논문 포스팅이 homepage에 추가된 뒤, Tier 1 exact ID matching(arXiv/DOI/Nature)으로 정확히 매칭되는 서베이 참고문헌에만 [#NN] 포스트 링크를 자동 삽입한다. '/link-post', 'survey에 포스트 연결', '서베이 포스트 링크', '/post 후속' 요청 시 사용. /post 스킬의 Step R12.7에서 자동 호출되어야 함."
---

# Link Post to Surveys — Tier 1 기반 포스트↔서베이 교차 연결

새 논문 포스트가 www.terryum.ai에 추가되었을 때, 연결된 비공개 `terry-surveys-contents`의 서베이에서 **같은 논문**(arXiv ID / DOI / Nature 아티클 ID 일치)을 찾아 해당 참고문헌 라인에 `[#NN](post-url)` 링크를 자동 삽입한다.

원고 수정 전에 framework의 `.codex/skills/survey/references/source-repositories.md`를 읽고 저장소 연결 및 비공개 원본 정책을 따른다. `terry-surveys/surveys`는 sibling contents 저장소로 연결된 경로다. 원고·생성 HTML·이미지를 공개 framework 저장소에 커밋하지 않는다.

**핵심 원칙**: false positive 0. slug 토큰 유사도로 엉뚱한 논문에 링크가 붙으면 서베이 신뢰도를 크게 해치므로, Tier 1 exact ID match만 자동 링크 대상이다. Tier 3 fuzzy 매칭은 사용자 확인 후에만 진행한다.

## 사용 예시

```
/link-post-to-surveys 2412-f-tac-hand
/link-post-to-surveys 2503-tacpalm-softhand
/link-post-to-surveys                     # 인자 생략 시 가장 최근 포스트
```

## Step 1) 인덱스 최신화

```bash
cd /Users/terrytaewoongum/Codes/personal/terry-surveys
python3 build.py --index       # refs_index.json (reverse_index 포함)
python3 bibtex/refs_index.py build-posts  # posts_index.json
```

- `--index`: 서베이 refs 인덱스 + 역인덱스(arxiv/doi/nature → 위치 매핑) 재빌드
- `build-posts`: 포스트 meta.json 스캔 후 포스트 인덱스 재빌드
- 초 단위로 완료 — 매번 재빌드 안전

## Step 2) Impact 분석 (Tier 1 + Tier 2)

```bash
python3 build.py --impact <post-slug>
```

출력 구조:
- **`## Tier 1 — already citing (exact ID match)`** — arXiv/DOI/Nature ID가 포스트와 서베이 ref에 겹치는 위치. **자동 링크 대상**. 마스터 bibtex를 경유해 DOI↔arXiv cross-reference도 bridge됨 (포스트 arXiv만 알고 RHT ref line은 DOI만 적혀 있어도 매칭).
- **`## Tier 2 — related chapters (keyword / topic)`** — 포스트 tags/subfields/key_concepts와 챕터 title/summary의 word overlap 점수. **자동 삽입 금지** — 사용자에게 "리프레시 후보"로 제시하고 승인 시에만 챕터 편집 제안.

포스트 meta.json에 arXiv/DOI/Nature 식별자가 없으면 Tier 1 비활성. Tier 2만 참고.

## Step 3) Tier 1 매칭 위치에 [#NN] 링크 삽입

각 Tier 1 hit은 `locations` 배열에 `survey/chapter/ref_num` 을 제공한다. 각 위치에 대해:

1. 해당 서베이의 `book/ko/ch<N>.md`와 `book/en/ch<N>.md`를 모두 편집 (언어 페어)
2. `## 참고문헌` (ko) / `## References` (en) 섹션에서 `<ref_num>.` 으로 시작하는 라인을 찾음
3. 그 라인에 포스트 링크가 이미 없는지 확인 (`[#` 토큰이 없으면 신규). **이미 있으면 스킵** — 중복 방지
4. `[scholar](...)` 직전에 포스트 링크 삽입:
   - ko: `[#<post_number>](https://www.terryum.ai/ko/posts/<slug>)`
   - en: `[#<post_number>](https://www.terryum.ai/en/posts/<slug>)`

`post_number`는 `bibtex/posts_index.json`의 해당 slug 엔트리에서 읽는다.

예시 — F-TAC (post #39, slug=`2412-f-tac-hand`, arxiv:2412.14482):

**Before** (`book/ko/ch02.md:197`):
```
17. Zhao, Z., et al. (2025). Embedding high-resolution touch across robotic hands... https://arxiv.org/abs/2412.14482 [scholar](...)
```

**After**:
```
17. Zhao, Z., et al. (2025). Embedding high-resolution touch across robotic hands... https://arxiv.org/abs/2412.14482 [#39](https://www.terryum.ai/ko/posts/2412-f-tac-hand) [scholar](...)
```

## Step 4) 본문 인라인 인용은 수정하지 않는다

**명시적 결정**: 본문의 `[Zhao et al., 2025]` 같은 인라인 인용은 **그대로 둔다**. 빌드 시 `shared/build_site.py`가 이를 `<sup><a class="cite-link" href="#ch<N>-ref-<M>">[M]</a></sup>`로 변환하여 페이지 내 참고문헌 섹션으로 스크롤시킨다. 독자는 참고문헌 라인에서 `[#NN]` 포스트 링크와 원본 arXiv/DOI 링크, scholar 링크를 함께 본다.

이 방식은 (a) 동일 논문이 한 챕터에 여러 번 인용돼도 링크를 한 곳(참고문헌)에 통합하고, (b) 본문이 링크로 어수선해지는 것을 방지한다.

## Step 5) 리빌드

변경된 서베이마다 HTML 재생성:

```bash
python3 build.py <affected-survey-name>
```

여러 서베이가 영향받으면 각각 실행. `--all`은 불필요.

## Step 6) 비공개 contents 저장소에 원고 변경 기록

모든 서베이는 `terryum/terry-surveys-contents`를 사용한다. 기존 개별 서베이 저장소나 과거 `push-private.sh` 경로를 재사용하지 않는다.

커밋·푸시가 요청된 작업이면 contents 저장소에서 `gh context`로 personal/terryum을 확인하고, `gh repo view terryum/terry-surveys-contents --json visibility,isPrivate`로 비공개 여부를 확인한다. 변경한 `surveys/<name>/book/`의 KO/EN 파일만 명시적으로 stage하여 커밋·푸시한다. 생성 `docs/`, `_workspace/`, 이미지 파일은 커밋하지 않는다. 링크 수정만으로 원고 전체를 재작성하지 않는다.

## Step 7) 검증과 게시 상태

변경된 원고는 이전 digest에 묶인 QA·배포 근거를 재사용할 수 없다. 게시까지 요청된 경우 canonical survey의 `references/quality-and-release.md`에 따라 현재 원고를 재검증하고 기존 preview/publication 절차를 따른다. 링크 삽입 요청만으로 새로운 공개 게시 권한을 추론하지 않는다. 소스 커밋과 라이브 게시 상태를 구분해 보고한다.

## /post 스킬과의 연동

활성 `$post` 또는 `$paper` 워크플로우가 이 작업을 위임할 때 현재 호출의 범위와 게시 권한을 따른다. 과거의 특정 step 번호나 설치 경로가 현재도 존재한다고 가정하지 않는다. 매칭 판정 규칙:

- **Tier 1 hit 있음** → 해당 참고문헌을 연결하고 검증한다. 커밋·게시 단계는 현재 호출에서 허용된 범위를 따른다.
- **Tier 1 없고 Tier 2만** → Tier 2 리포트를 사용자에게 제시, "이 챕터들을 신규 paper로 업데이트할까요?"로 승인 받은 항목만 편집
- **아무 매칭 없음** → 조용히 종료

## 반대 방향: 새 서베이 추가 시 기존 포스트 연결

canonical `$survey`의 링크 정비 단계에서 같은 exact-ID 매칭으로 기존 포스트를 연결한다. KO/EN에 `[#NN]`을 삽입하고 재빌드·검증한 뒤, 현재 run의 contents 커밋과 release 절차를 따른다.

## 중복·에러 처리

- 참고문헌 라인에 이미 `[#<number>]` 가 있으면 스킵 (같은 포스트 재호출 idempotent)
- 다른 포스트 번호 링크(`[#40]`)가 이미 있는데 새로 `[#41]`을 넣어야 하는 경우는 **해당 ref가 서로 다른 논문을 같은 라인에 혼입한 버그**이므로 경고 출력, 자동 삽입 거부
- `bibtex/posts_index.json`에 slug 엔트리가 없으면 (/post 파이프라인이 미완료된 상태) 즉시 실패 + 명확한 에러 메시지

## 주의사항

- `bibtex/refs_index.json`과 `bibtex/posts_index.json`은 **gitignored**. 필요할 때마다 build-all로 재생성
- arXiv/DOI/Nature ID가 모두 없는 특수 논문(블로그 포스트, 기술 보고서 등)은 Tier 1 적용 불가 → 사용자 확인 필수
- Nature DOI(`10.1038/sXXXXX-...`)와 nature.com 아티클 ID(`sXXXXX-...`)는 `extract_paper_ids`에서 양방향 bridge됨 — 같은 논문이 DOI URL과 nature.com URL로 혼용돼도 매칭됨
