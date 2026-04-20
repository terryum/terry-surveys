---
name: link-post-to-surveys
description: "새 논문 포스팅이 homepage에 추가된 뒤, Tier 1 exact ID matching(arXiv/DOI/Nature)으로 정확히 매칭되는 서베이 참고문헌에만 [#NN] 포스트 링크를 자동 삽입한다. '/link-post', 'survey에 포스트 연결', '서베이 포스트 링크', '/post 후속' 요청 시 사용. /post 스킬의 Step R12.7에서 자동 호출되어야 함."
---

# Link Post to Surveys — Tier 1 기반 포스트↔서베이 교차 연결

새 논문 포스트가 www.terryum.ai에 추가되었을 때, terry-surveys 모노레포의 모든 서베이에서 **같은 논문**(arXiv ID / DOI / Nature 아티클 ID 일치)을 찾아 해당 참고문헌 라인에 `[#NN](post-url)` 링크를 자동 삽입한다.

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
python3 bibtex/refs_index.py build-all
```

- `build-all`: 서베이 refs 인덱스(`bibtex/refs_index.json`)와 포스트 인덱스(`bibtex/posts_index.json`)를 함께 재빌드
- 두 인덱스 모두 arXiv ID / DOI / Nature 아티클 ID를 추출하여 저장
- 초 단위로 완료되므로 매번 재빌드 안전

## Step 2) Tier 1 매칭 조회

```bash
python3 bibtex/refs_index.py match <post-slug>
```

출력 구조:
- **`✅ Tier 1 (exact ID match)`** 섹션 — `arxiv:...`, `doi:...`, `nature:...` 중 적어도 하나가 포스트 `source_url`과 서베이 ref 양쪽에 동일하게 존재. **이 섹션의 모든 항목만 자동 링크 대상**.
- **`⚠️  Tier 3 (slug-token fuzzy — REQUIRES HUMAN REVIEW)`** 섹션 — 제목·키워드 토큰 overlap 기반 fallback. 자동 링크 **금지**. 이 섹션은 사용자에게 제시하고 "yes"를 받았을 때만 해당 ref를 편집한다.

포스트 meta.json에 arXiv/DOI/Nature 식별자가 없으면 경고가 출력되고 Tier 1이 비활성화된다. 그 경우엔 Tier 3도 자동 삽입 금지 — 수동 확인 필수.

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

## Step 6) snu-tactile-hand 특수 처리 (private Cloudflare Pages 배포)

`snu-tactile-hand`는 `.gitignore`로 공개 repo에서 제외되고, 별도 private repo(`terryum/survey-snu-largescale-tactile-hand`)에서 Cloudflare Pages가 배포를 서빙한다. 링크 삽입 + 리빌드 후 반드시:

```bash
bash surveys/snu-tactile-hand/scripts/push-private.sh "link post <slug> (#<N>) to snu-tactile-hand"
```

이 스크립트가 private repo를 임시 clone → book/, docs/, assets/ 를 rsync → commit + push → Cloudflare Pages 자동 재배포 트리거 → 임시 dir 삭제 순서로 돌린다.

snu-tactile-hand이 Tier 1 매칭에 없으면 이 단계는 생략.

## Step 7) terry-surveys 공개 변경분 push

snu-tactile-hand 외의 서베이(robot-hand-tactile-sensor, vla-agentic-robotics 등) 변경분은 terry-surveys 공개 repo에 push:

```bash
git add surveys/<name>/book/ surveys/<name>/docs/
git commit -m "feat: link post <slug> (#<N>) to <survey> refs"
git push origin main
```

## /post 스킬과의 연동

`terryum-ai/.claude/skills/post/SKILL.md`의 Step R12.7이 이 스킬을 자동 호출한다. R12.7의 판정 규칙:

- **Tier 1 hit 있음** → 즉시 `/link-post-to-surveys <slug>` 실행 (Step 1~7 모두 자동)
- **Tier 3만 있음** → 사용자에게 매칭 후보 제시, 확인 후에만 수동 진행
- **아무 매칭 없음** → 조용히 종료

## 반대 방향: 새 서베이 추가 시 기존 포스트 연결

`/survey` 스킬 Step 5.5가 처리. `cite-post` 스킬을 호출하여 해당 서베이의 모든 ref를 순회하고 기존 포스트와 매칭 → `[#NN]` 삽입 → 리빌드 → (snu이면) private push.

## 중복·에러 처리

- 참고문헌 라인에 이미 `[#<number>]` 가 있으면 스킵 (같은 포스트 재호출 idempotent)
- 다른 포스트 번호 링크(`[#40]`)가 이미 있는데 새로 `[#41]`을 넣어야 하는 경우는 **해당 ref가 서로 다른 논문을 같은 라인에 혼입한 버그**이므로 경고 출력, 자동 삽입 거부
- `bibtex/posts_index.json`에 slug 엔트리가 없으면 (/post 파이프라인이 미완료된 상태) 즉시 실패 + 명확한 에러 메시지

## 주의사항

- `bibtex/refs_index.json`과 `bibtex/posts_index.json`은 **gitignored**. 필요할 때마다 build-all로 재생성
- arXiv/DOI/Nature ID가 모두 없는 특수 논문(블로그 포스트, 기술 보고서 등)은 Tier 1 적용 불가 → 사용자 확인 필수
- Nature DOI(`10.1038/sXXXXX-...`)와 nature.com 아티클 ID(`sXXXXX-...`)는 `extract_paper_ids`에서 양방향 bridge됨 — 같은 논문이 DOI URL과 nature.com URL로 혼용돼도 매칭됨
