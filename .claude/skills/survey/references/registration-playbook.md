# MODE B — Registration Playbook

`/survey <URL>` 또는 `/survey --register ...`가 호출됐을 때 실행되는 **기존 배포 서베이를 홈페이지 갤러리에 등록**하는 단계별 세부 가이드. 이 로직은 직전까지 `terryum-ai/.claude/skills/survey/SKILL.md`가 담고 있었고, 이번 리팩터링에서 이 파일로 이동했다. SKILL.md 본문은 이 문서를 요약 포인터로만 가리킨다.

## 입력

```
/survey <URL> [--featured] [--status=active|archived|wip] [--visibility=group --group=snu]
/survey --title="..." --embed="..." [기타 메타 수동 옵션]
```

## 공개 범위 (visibility) 옵션

- `--visibility=group --group=snu` → 그룹 전용 서베이
  - **surveys.json에 추가하지 않음** — Supabase `private_content` 테이블에 직접 저장.
  - `content_type: 'surveys'`, `group_slug`, `meta_json` (전체 SurveyMeta 객체).
  - 커버 이미지 → Supabase Storage `private-covers/{slug}/cover.webp`.
  - **Git 커밋/푸시 불필요.**
- 기본값: `visibility: "public"` (surveys.json에 저장, Git 커밋).

## Step 0) 배포 플랫폼 (Cloudflare Pages 전용)

**공개 서베이**: 해당 survey repo를 Cloudflare Pages에 연결
- Dashboard → Pages → Connect to Git → survey repo 선택 → Production branch: `main` → Build output: `docs/`.
- 배포 URL: `<project-name>.pages.dev` → 이 URL을 `embed_url`로 사용.

**비공개(그룹) 서베이**: private repo → Cloudflare Pages Direct Upload (`wrangler pages deploy`).

## Step 1) URL / 정보 수집

- Cloudflare Pages URL 또는 embed URL 제공 시 → WebFetch로 사이트 접속하여 목차·소개글 추출.
- GitHub URL 제공 시 → README에서 목차·설명 추출.
- `--title`, `--embed`, `--toc` 등 수동 옵션도 허용.

## Step 2) 메타데이터 구성

```json
{
  "slug": "book-example",
  "survey_number": N,
  "title": { "ko": "...", "en": "..." },
  "description": { "ko": "...", "en": "..." },
  "cover_image": "/images/projects/{slug}-cover.webp",
  "tech_stack": ["Robotics", "Survey"],
  "toc": ["Chapter 1", "Chapter 2", "..."],
  "links": [
    { "type": "demo", "url": "https://...", "label": "Read" },
    { "type": "github", "url": "https://github.com/..." }
  ],
  "embed_url": "https://...",
  "status": "active",
  "featured": true,
  "order": 0,
  "published_at": "2026-01-01"
}
```

### 필드 규약
- `survey_number`: `surveys.json`의 `next_survey_number`를 사용 후 증가.
- `toc`: 이중 언어 `{ ko, en }[]` 형식. 사이트/README에서 추출 후 번역.
  - **한글 목차 제목**: 공백 포함 **12자** 이내 (카드 truncation 방지).
  - **영문 목차 제목**: 공백 포함 **19자** 이내.
  - 구분자는 ` — `(em dash) 대신 `: `(colon) 사용 — 폭 절약.
  - 초과 시 약어나 짧은 표현으로 조정.
- `description`: 한글/영어 각각 **2–3줄** (카드에서 5–7줄 이내로 보이도록).

## Step 3) 이미지 생성 — gpt-image-2 medium cover 1장 + utility로 og/thumb 자동 derive

**핵심 원칙**: 사람은 cover 1장만 정성껏 생성한다. og.png + thumb.webp는 `process-content-images.mjs` utility가 자동 파생. 이렇게 해야 4-asset spec이 항상 동일하게 강제됨.

### 4-Asset 표준 spec (post / survey / project 공통)

| 자산 | 해상도 | 포맷 | quality | 목표 크기 | 용도 |
|---|---|---|---|---|---|
| **cover** | 1200×1200 (survey/project, 1:1 정사각) / 1200×variable (post) | WebP | q90 | ≤500 KB | 상세 페이지 hero |
| **og** | 1200×630 | PNG | q90, comp 8 | ≤500 KB (Bluesky 1MB 안전) | 소셜 공유 |
| **thumb** | 288×288 cover-centre | WebP | q80 | ≤20 KB | 홈페이지 카드 |

모든 자산은 **flatten white background** 적용 (다크모드 안전, alpha 채널 없음).

### 단계

```bash
# 1) OpenAI gpt-image-2 medium으로 cover 1장만 1:1로 생성 (raw 2K, ~2MB)
python3 ~/.claude/skills/image-gen/scripts/generate-image.py \
  "<v3 prompt — 아래 가이드>" \
  --style darkmode --ratio 1:1 --quality medium \
  -o /Users/terrytaewoongum/Codes/personal/terryum-ai/public/images/projects/{slug}-cover.webp

# 2) utility가 cover를 표준 spec으로 압축 + og.png + thumb.webp 자동 파생
cd /Users/terrytaewoongum/Codes/personal/terryum-ai
node scripts/process-content-images.mjs --type=survey --slug={slug} --force
```

`process-content-images.mjs` 동작:
- cover.webp가 raw gpt-image-2 출력이면 1200×1200 WebP q90으로 재처리 → ~140 KB
- cover.webp에서 og.png 1200×630 자동 파생 → ~300 KB
- cover.webp에서 thumb.webp 288×288 자동 파생 → ~13 KB
- 이미 표준 spec이면 skip (idempotent)
- `--force`: 기존 자산이 spec 충족이어도 재처리

### Prompt 가이드 — 풀블리드 + 디테일 동시 달성 (2026-04-28 사고 후 v3 patterns)

cover.webp 생성 시 **다섯 규칙**을 모두 지킨다 — 한 가지라도 빠지면 풀블리드가 무너지거나 디테일이 사라진다:

**규칙 1: `--style darkmode` preset 필수**
> darkmode preset은 prompt 앞에 "deep dark background, glowing accent colors, dark UI aesthetic"을 prepend해서 톤 일관성을 잡아준다. 빠지면 generic하고 평면적인 결과.

**규칙 2: subject 구성요소를 이름으로 명시 (추상화 금지)**
> ✅ `CLAUDE.md and subagent configuration in cyan glow, AGENTS.md and Codex CLI in orange glow, an LLM Wiki knowledge-brain structure`
> ❌ "two AI coding terminal windows", "abstract neural dependency graph"
> gpt-image-2도 구체적 명사를 받으면 디테일을 거기에 쏟는다. 추상화될수록 디테일이 빠진다 (V2 사고 — 풀블리드 만들었지만 디자인이 약해진 원인).

**규칙 3: edge-to-edge composition 한 줄로 명시 (긴 명령 금지)**
> ✅ `"Edge-to-edge composition, no book mockup, no frame, no shadow."` (3 negatives)
> ❌ `"Cinematic full-bleed... no book mockup, no book cover, no frame, no border, no shadow, no isometric book, no surrounding background. Subject must touch all four edges of the canvas."` (7+ negatives + layout constraint)
> Negative prompt 7개+ 면 모델이 negative 처리에 budget을 써서 positive composition quality가 깎인다.

**규칙 4: 금지어 절대 안 씀**
> "book cover", "book mockup", "square book", "Clean upper area for title overlay" → 모델이 책 표지 + 회색 배경 + 그림자를 그리기 쉽다. "title overlay" 힌트가 책 위쪽 비우기 효과를 만들어 book-mockup 레이아웃을 유도하는 trigger.

**규칙 5: 끝에 "deep dark background"가 아니라 specific gradient 명시**
> ✅ `"Deep midnight blue to purple gradient"` 또는 `"Deep navy blue background"`
> ❌ "dark background" (너무 generic하면 이미지 내 contrast 약해짐)

**Canonical 템플릿** (cover.webp 1:1):

```
"<Subject 1 with concrete name and color>, <Subject 2 with concrete name
and color>, <connecting/background concrete element>. <Specific gradient>.
Edge-to-edge composition, no book mockup, no frame, no shadow."
--style darkmode --ratio 1:1
```

**실증 예 (S5 claude-to-codex v3, 결과 검증됨)**:

```
"Two AI coding terminal windows filling the canvas side by side — the
left one displays CLAUDE.md and subagent configuration in cyan glow, the
right one displays AGENTS.md and Codex CLI in orange glow. An agent
dependency graph with glowing cyan connection arrows weaves between
them. An LLM Wiki knowledge-brain structure glows in the background.
Deep midnight blue to purple gradient. Edge-to-edge composition, no book
mockup, no frame, no shadow."
--style darkmode --ratio 1:1
```

**OG는 별도 image call 필요 없음** — `process-content-images.mjs`가 cover.webp에서 1200×630 PNG로 자동 파생 (~300 KB). 별도 16:9 prompt 짤 필요 없음. 기본 생성은 OpenAI `gpt-image-2` `medium`; Terry가 결과물 불만족으로 재생성을 지시할 때만 `high`.

**왜 utility 한 곳에서 다 처리하는가** (2026-04-28 사고 가족):
- 사고 가족: 무압축 cover (2.4 MB) → Bluesky 1MB blob 실패; thumb 누락 → 홈 카드 broken image; og 1200×630 아님 → Facebook scraper reject. 전부 사람이 압축/derive 단계를 빼먹어서 발생.
- utility가 spec을 강제하면 위 사고 모두 사라짐.
- 동일 utility를 `/post` (terry-obsidian)도 호출 — post + survey 자산 표준 100% 동일.

공유 URL: `/surveys/{slug}` (lang 없는 경로) → 자동 리다이렉트 + OG 메타태그 제공 (og.png 사용).

## Step 4) surveys.json 업데이트

`projects/surveys/surveys.json`의 `surveys` 배열에 엔트리 추가.
`next_survey_number` 증가.

## Step 5) 빌드 + 검증

```bash
npx tsc --noEmit
npm run build
```

## Step 5.5) 기존 포스트 역참조 — 자동 호출

등록되는 서베이가 terry-surveys 모노레포의 서베이 책을 가리키는 경우 (`github_repo` 또는 `embed_url`이 `terry-surveys/surveys/<name>/` 또는 관련 private repo), **해당 서베이 책의 참고문헌과 www.terryum.ai 기존 포스트를 매칭하여 본문 인용과 ref에 `[#NN]` 링크를 자동 삽입한다**.

```bash
# 1) 대상 서베이 디렉토리 확인
SURVEY_DIR=/Users/terrytaewoongum/Codes/personal/terry-surveys/surveys/<survey-slug-or-name>
[ -d "$SURVEY_DIR" ] || { echo "not a terry-surveys book — skip"; exit 0; }

# 2) terry-surveys로 이동 후 cite-post 스킬 호출
cd /Users/terrytaewoongum/Codes/personal/terry-surveys
```

그 다음 **`/cite-post <survey-name>`** 스킬을 호출한다. cite-post는:
- `terryum-ai/posts/papers/` 전수 스캔 → `meta.json`에서 slug·postNumber·제목·저자 수집.
- `surveys/<name>/book/{ko,en}/ch*.md`의 `## 참고문헌` / `## References` 파싱.
- 제목·저자 매칭된 각 ref에 `[#NN](https://www.terryum.ai/{ko|en}/posts/{slug})` 삽입.
- (선택) 인라인 인용에도 동일 링크 삽입.

완료 후 리빌드 및 (필요 시) private push:

```bash
# 3) 리빌드
python3 build.py <survey-name>

# 4) snu-tactile-hand 계열이면 private repo로 push (Cloudflare Pages 자동 재배포)
if [ "<survey-name>" = "snu-tactile-hand" ]; then
  bash surveys/snu-tactile-hand/scripts/push-private.sh "link existing posts to snu-tactile-hand refs"
fi
```

- terry-surveys 모노레포의 **공개 변경분**(CLAUDE.md, bibtex/, shared/ 등)만 별도 커밋 + push.
- `surveys/snu-tactile-hand/book/` 및 `docs/`는 `.gitignore`로 공개 repo에서 제외되므로 private 스크립트로만 반영.
- 서베이 디렉토리가 없거나 cite-post가 실패하면 경고만 출력하고 이 단계 스킵 (비차단).

## Step 6) Git 커밋 + 푸시 (public만)

```bash
git pull --rebase origin main
git add projects/surveys/ public/images/projects/
git commit -m "feat(survey): add {slug}"
git push
```

- **`git pull --rebase` 필수**: terry-surveys 등 다른 워크스페이스에서 동시에 push했을 수 있으므로, 커밋 전 최신 상태를 먼저 가져온다.
- push 실패 시 `git pull --rebase` 후 재시도.

## Step 7) GHA 배포 검증 (필수 — skip 금지)

`git push`는 GitHub Actions의 `Deploy to Cloudflare Workers` workflow를 트리거하지만, **CI 빌드는 로컬과 환경이 달라 실패할 수 있다**. 로컬 `npm run build` 통과만으로는 라이브 배포 성공을 보장하지 않는다.

```bash
# 1) Push 후 30초 대기, 트리거된 run 식별
sleep 30
RUN_ID=$(gh run list --limit 1 -R terryum/terryum-ai --workflow=deploy.yml --json databaseId -q '.[0].databaseId')

# 2) 완료까지 watch (실패 시 non-zero 반환)
gh run watch "$RUN_ID" -R terryum/terryum-ai --exit-status
```

성공 시 다음 단계로 진행. **실패 시 진단 → 수정 → 재push → 다시 Step 7**:

```bash
# 실패 로그 확인
gh run view "$RUN_ID" -R terryum/terryum-ai --log-failed | tail -100

# 흔한 실패 후보:
# (a) 로컬은 통과한 빌드가 CI 캐시 stale로 실패 — 가장 흔함
#     → `gh workflow run deploy.yml -R terryum/terryum-ai` 로 workflow_dispatch 재트리거.
#        2026-04-28 사고: surveys.json 변경 push가 transient CI 캐시 문제로 실패,
#        workflow_dispatch 재실행으로 즉시 복구.
# (b) surveys.json 새 entry의 어떤 필드가 빌드 시 undefined.length 트리거
#     → 기존 entry와 schema 비교 후 누락 필드 채우거나 surveys.ts loader에 ?. guard 추가.
# (c) 환경 변수(시크릿) 누락 — 워크플로우 env 섹션 점검.
```

**핵심 규칙**: 사용자에게 "완료" 보고하기 전에 **반드시 GHA success를 확인**한다. push 자체가 곧 deploy 성공을 의미하지 않는다.

## Step 8) 라이브 노출 확인 (필수)

GHA success 직후, 새 슬러그가 실제 사이트에 노출되는지 검증:

```bash
SLUG="survey-{slug}"
curl -s https://www.terryum.ai/en/surveys | grep -q "$SLUG" && echo "EN surveys OK" || echo "EN MISS"
curl -s https://www.terryum.ai/ko/surveys | grep -q "$SLUG" && echo "KO surveys OK" || echo "KO MISS"
curl -sI "https://www.terryum.ai/en/surveys/$SLUG" | head -1  # 200 OK 기대
```

여전히 MISS면:
1. **5–10분 대기** (Cloudflare R2 ISR cache TTL 만료)
2. **manual purge**: Cloudflare Dashboard → Cache → Purge Cache (특정 URL 또는 Everything)
3. 재확인. 그래도 안 되면 R2 incremental cache의 stale buildId 추적 (deploy.yml의 `r2-cache-gc.mjs` 동작 점검)

## 검증 체크리스트

- [ ] `surveys.json`에 새 엔트리 추가, `survey_number` 증가 일관성
- [ ] **세 이미지 자산 모두 생성**: `{slug}-cover.webp` (1:1) + `{slug}-og.jpg` (16:9) + **`{slug}-thumb.webp` (288×288, homepage Featured 카드용 — 누락 시 broken image)**
- [ ] `description` 길이 (ko 2–3줄, en 2–3줄)
- [ ] `toc` 길이 (ko ≤12자, en ≤19자 per item)
- [ ] terry-surveys 연관 시 `/cite-post` 자동 호출 완료
- [ ] `npx tsc --noEmit` 통과
- [ ] `npm run build` 성공 (로컬)
- [ ] Git pull --rebase 후 push 성공 (public only)
- [ ] **GHA `Deploy to Cloudflare Workers` run success** (Step 7)
- [ ] **라이브 사이트(www.terryum.ai)에 새 slug 노출** (Step 8 — KO/EN/상세페이지 셋 다)
