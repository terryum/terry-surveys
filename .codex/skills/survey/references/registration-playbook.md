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

**공개 서베이 기본값**: terry-surveys 안의 `surveys/<slug>/docs/`를
Cloudflare Pages Direct Upload로 배포한다. GitHub repo 연결 방식도 허용되지만,
Codex가 즉시 끝내야 하는 `$survey` 배포에서는 direct upload가 표준이다.

```bash
cd /Users/terrytaewoongum/Codes/personal/terry-surveys
python3 build.py <survey-dir>
bash surveys/<survey-dir>/scripts/push.sh "deploy <survey-dir>"
```

`wrangler pages deploy`가 `Project not found`로 실패하면 중단하지 말고 Pages
프로젝트를 만든 뒤 같은 push script를 다시 실행한다.

```bash
npx wrangler pages project create <pages-project-name> --production-branch main
bash surveys/<survey-dir>/scripts/push.sh "deploy <survey-dir>"
```

배포 URL은 `https://<pages-project-name>.pages.dev/`이고, 이 URL을
`terryum-ai`의 `embed_url`로 사용한다. `scripts/push.sh`의 `PROJECT_NAME`과
`survey.json`/gallery slug가 다를 수 있으므로 둘을 혼동하지 않는다.

**Git 연결 대안**: 해당 survey repo를 Cloudflare Pages에 연결
- Dashboard → Pages → Connect to Git → survey repo 선택 → Production branch:
  `main` → Build output: `docs/`.
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
- `_qa_report.md`가 `BLOCKED:`로 끝나는 draft를 사용자가 명시적으로 배포하라고
  한 경우, public gallery 등록은 허용하되 `status: "wip"`을 기본값으로 사용한다.
  이때 배포 완료 보고는 "WIP/draft preview"라고 말해야 하며 release-ready라고
  말하면 안 된다.

## Step 3) 이미지 생성 — gpt-image-2 medium cover 1장 + utility로 og/thumb 자동 derive

**핵심 원칙**: 사람은 cover 1장만 정성껏 생성한다. og.png + thumb.webp는 `process-content-images.mjs` utility가 자동 파생. 이렇게 해야 4-asset spec이 항상 동일하게 강제됨.

### 4-Asset 표준 spec (post / survey / project 공통)

| 자산 | 해상도 | 포맷 | quality | 목표 크기 | 용도 |
|---|---|---|---|---|---|
| **cover** | 1200×1200 (survey/project, 1:1 정사각) / 1200×variable (post) | WebP | q90 | ≤500 KB | 상세 페이지 hero |
| **og** | 1200×630 | PNG | q90, comp 8 | ≤500 KB (Bluesky 1MB 안전) | 소셜 공유 |
| **thumb** | 288×288 cover-centre | WebP | q80 | ≤20 KB | 홈페이지 카드 |

모든 자산은 **flatten white background** 적용 (다크모드 안전, alpha 채널 없음).

### Gallery style gate — 기존 survey 카드와 같은 톤 유지

서베이 gallery cover/OG/thumb는 chapter figure가 아니라 홈페이지 카드와 소셜
공유용 브랜드 자산이다. 기존 S1/S4/S6/S9 스타일과 맞춰야 한다.

- **허용**: 어두운 full-bleed 배경, 텍스트 없는 단일 주제 비주얼, 로봇/데이터/도메인
  subject가 중앙 1:1 thumb와 1200×630 OG crop에서 모두 살아있는 이미지.
- **금지**: 흰 배경 슬라이드, 표/매트릭스/diagram export, 스크린샷, 작은 글자가 많은
  infographic, 잘린 로고/텍스트, 카드 안에서만 읽히는 설명형 이미지.
- cover는 사람이 정성껏 고르고, og/thumb는 반드시 utility로 파생한다. thumb를 따로
  손으로 만들지 않는다.
- 새 자산을 만든 뒤 반드시 실행:

```bash
python3 ~/.codex/skills/survey/scripts/validate_gallery_assets.py {slug}
```

이 검증은 해상도/포맷/alpha와 함께 기존 survey cover 대비 과도한 밝기·흰 배경을
잡는다. 실패하면 `terryum-ai` 등록이나 redeploy로 넘어가지 않는다.

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

# 3) 기존 survey gallery 스타일과 spec 검증
python3 ~/.codex/skills/survey/scripts/validate_gallery_assets.py {slug}
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
- 로컬 변경이 있어 `git pull --rebase`가 막히면 먼저 `git fetch origin main`과
  `git rev-list --left-right --count HEAD...origin/main`으로 divergence를 확인한다.
  `0 0`이면 현재 변경만 커밋해도 된다. 원격이 앞서 있으면 unrelated local dirty
  files를 건드리지 말고 사용자의 변경을 보존한 채 stash/commit 전략을 명확히
  선택한다.

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

## Step 8) 라이브 노출 확인 (필수 — HTTP 200만으로 통과 금지)

GHA success 또는 로컬 Worker deploy 직후, 새 슬러그가 실제 사이트에
노출되는지 **본문 내용으로** 검증한다. Next/OpenNext는 라우트 실패 시에도
HTTP 200으로 `Page Not Found` tree를 스트리밍할 수 있으므로 `curl -I`나
status code만 확인하면 안 된다.

```bash
SLUG="survey-{slug}"
EMBED="https://{survey-pages-project}.pages.dev/"
TMP="${TMPDIR:-/tmp}/survey-live-check-$SLUG"
mkdir -p "$TMP"

curl -sS -D "$TMP/detail.ko.headers" \
  -o "$TMP/detail.ko.html" \
  "https://www.terryum.ai/ko/surveys/$SLUG"
curl -sS -D "$TMP/list.ko.headers" \
  -o "$TMP/list.ko.html" \
  "https://www.terryum.ai/ko/surveys"
curl -sS -D "$TMP/detail.en.headers" \
  -o "$TMP/detail.en.html" \
  "https://www.terryum.ai/en/surveys/$SLUG"
curl -sS -D "$TMP/list.en.headers" \
  -o "$TMP/list.en.html" \
  "https://www.terryum.ai/en/surveys"

# Detail page must embed the survey, not merely return 200.
grep -q "$EMBED" "$TMP/detail.ko.html"
grep -q "$EMBED" "$TMP/detail.en.html"

# List pages must include the new survey entry.
grep -q "$SLUG" "$TMP/list.ko.html"
grep -q "$SLUG" "$TMP/list.en.html"

# No active Next/OpenNext 404 fallback is allowed. Serialized inactive
# `notFound` templates may contain "Page Not Found"; do not fail on that string
# alone when the expected iframe/list content is present.
! grep -q "NEXT_HTTP_ERROR_FALLBACK;404" "$TMP/detail.ko.html"
! grep -q "NEXT_HTTP_ERROR_FALLBACK;404" "$TMP/detail.en.html"
```

권장 요약 검증:

```bash
node -e "const urls=[
  'https://www.terryum.ai/ko/surveys/$SLUG',
  'https://www.terryum.ai/en/surveys/$SLUG',
  'https://www.terryum.ai/ko/surveys',
  'https://www.terryum.ai/en/surveys',
  '$EMBED/ko/',
  '$EMBED/en/'
]; (async()=>{for(const u of urls){const r=await fetch(u); const t=await r.text();
  console.log(u);
  console.log('  status', r.status);
  console.log('  has slug', t.includes('$SLUG'));
  console.log('  has embed', t.includes('$EMBED'.replace(/^https?:\/\//,'')));
  console.log('  active404', t.includes('NEXT_HTTP_ERROR_FALLBACK;404'));
}})().catch(e=>{console.error(e); process.exit(1);})"
```

검증 실패 시 아래 순서로 처리한다.

1. **현재 배포 Worker가 새 `surveys.json`을 포함했는지 확인**
   - `/Users/terrytaewoongum/Codes/personal/terryum-ai/projects/surveys/surveys.json`
     에 `$SLUG`가 있는지 확인한다.
   - `.open-next` 또는 `.next` 산출물에서 `$SLUG`를 `rg`로 확인한다.
   - `npx wrangler deployments status --name terry-artlab-homepage`로 현재
     production version 생성 시각이 새 등록 변경 이후인지 확인한다.

2. **등록 변경이 포함된 working tree에서 다시 빌드/배포**
   - 로컬 direct deploy를 쓰는 경우:
     `npm run build` 후 `npm run deploy:cf`.
   - GitHub Actions 배포를 쓰는 경우:
     `git status --short`로 `projects/surveys/surveys.json`과 이미지 자산이
     staged/committed/pushed 되었는지 확인하고, 누락 시 커밋/푸시 후 Step 7부터
     다시 수행한다.

3. **OpenNext R2 incremental cache 정리**
   - 최신 Worker 배포 직후 아래를 실행한다.

   ```bash
   cd /Users/terrytaewoongum/Codes/personal/terryum-ai
   node scripts/r2-cache-gc.mjs --dry-run --keep 1
   node scripts/r2-cache-gc.mjs --apply --keep 1
   ```

4. **Step 8 live HTML assertion 재실행**
   - 모든 `grep` assertion이 통과할 때까지 완료 보고 금지.

**사고 메모 (2026-06-08)**: `survey-nvidia-physical-ai-robotics` 등록 시
standalone Pages와 Worker deploy는 성공했지만, production Worker bundle의
`surveys.json`이 새 S9 entry를 포함하지 않아 `/ko/surveys/<slug>`가
HTTP 200으로 `Page Not Found`를 렌더링했다. R2 cache 삭제만으로는 해결되지
않았고, S9 entry가 들어 있는 working tree에서 `terryum-ai`를 재빌드/재배포한
뒤 stale R2 prefix를 지우고 live HTML assertion을 수행해야 했다.

## 검증 체크리스트

- [ ] `surveys.json`에 새 엔트리 추가, `survey_number` 증가 일관성
- [ ] **세 이미지 자산 모두 생성**: `{slug}-cover.webp` (1:1) + `{slug}-og.png` (1200×630) + **`{slug}-thumb.webp` (288×288, homepage Featured 카드용 — 누락 시 broken image)**
- [ ] `description` 길이 (ko 2–3줄, en 2–3줄)
- [ ] `toc` 길이 (ko ≤12자, en ≤19자 per item)
- [ ] terry-surveys 연관 시 `/cite-post` 자동 호출 완료
- [ ] `npx tsc --noEmit` 통과
- [ ] `npm run build` 성공 (로컬)
- [ ] Git pull --rebase 후 push 성공 (public only)
- [ ] **GHA `Deploy to Cloudflare Workers` run success** (Step 7)
- [ ] **라이브 사이트(www.terryum.ai)에 새 slug 노출** (Step 8 — KO/EN list + KO/EN detail)
- [ ] **상세 HTML에 iframe `src` 존재** 및 `NEXT_HTTP_ERROR_FALLBACK;404` 부재
- [ ] terry-surveys 원본도 새 survey 디렉터리만 커밋/푸시되어 gallery GitHub 링크와 실제 source가 일치
- [ ] 필요 시 `scripts/r2-cache-gc.mjs --apply --keep 1` 실행 후 Step 8 재검증
