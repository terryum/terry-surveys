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

## Step 3) 이미지 생성 — 3개 (cover + og + thumb)

`/image-gen` 스킬로 두 이미지를 생성한 뒤, **third asset (thumb.webp)을 sharp로 직접 derive**한다. 세 자산은 각자 다른 페이지/소비처에서 쓰인다 — 누락 시 화면 깨짐:

### Prompt 가이드 — 책 mockup 절대 금지 (2026-04-28 사고)

`/image-gen` 호출 시 prompt에 **"book cover", "book mockup", "square book"** 같은 표현을 **쓰지 말 것**. Gemini가 받으면 책 표지 illustration을 회색/흰 배경 위에 그림자와 함께 렌더링해 버리고, 결과적으로 홈페이지 Featured Surveys 카드에 가운데 작은 책 + 큰 여백 + 그림자가 보인다. S1–S3 서베이는 풀블리드 일러스트인데 S4 (humanoid-revolution) · S5 (claude-to-codex)는 책 mockup으로 등록되어 카드 정렬이 깨진 사고가 있었다.

**Anti-mockup directives — prompt 끝에 항상 명시**:

```
Cinematic full-bleed concept art, edge-to-edge composition filling entire square canvas.
[main subject description]
Pure conceptual illustration. No book mockup, no book cover, no frame, no border,
no shadow, no isometric book, no surrounding background. Subject must touch all
four edges of the canvas.
```

**`--style darkmode`만으로는 부족**: darkmode preset은 다크 톤은 잡아주지만 책 mockup을 막지 않는다. anti-mockup 문구를 prompt 본문에 명시.

규칙 위반 시 사후 수정 비용: ₩200 × 2 (cover 재생성) + ₩0 (thumb 재파생) + GHA 한 번 + Cloudflare cache 회복 대기 = 사고 한 번이 ~₩500 + 시간. prompt 한 줄 추가가 훨씬 싸다.

1. **커버 이미지** (정사각형, 1:1): 서베이 상세 페이지 hero, 갤러리 카드 fallback.
   - `public/images/projects/{slug}-cover.webp` (public) 또는 Supabase Storage (group).
2. **OG 이미지** (1200×630, 16:9): 소셜 공유용 대표 이미지.
   - `public/images/projects/{slug}-og.jpg` (public) 또는 Supabase Storage (group).
   - JPEG 형식 (X/Twitter 호환).
3. **썸네일** (288×288, 2x retina for 144px display): **홈페이지 Featured Surveys 카드의 실제 표시 이미지**.
   - `public/images/projects/{slug}-thumb.webp` (public).
   - cover.webp에서 sharp로 resize-cover-centre crop:
     ```bash
     cd /Users/terrytaewoongum/Codes/personal/terryum-ai && node -e "
     import('sharp').then(async ({default:s})=>{await s('public/images/projects/{slug}-cover.webp')
       .resize(288,288,{fit:'cover',position:'centre'}).webp({quality:85})
       .toFile('public/images/projects/{slug}-thumb.webp')})"
     ```

**왜 thumb.webp가 별도로 필요한가**: `src/app/[lang]/page.tsx` Featured Surveys 컴포넌트가 `cover_image.replace('-cover.webp','-thumb.webp')`로 thumb URL을 강제 사용한다 (string replacement, not file-existence fallback). thumb.webp 누락 시 카드가 broken image. 2026-04-28 사고 — survey-claude-to-codex 등록 시 cover/og만 생성하고 thumb 누락. 다른 4개 서베이는 모두 thumb.webp가 존재했다.

공유 URL: `/surveys/{slug}` (lang 없는 경로) → 자동 리다이렉트 + OG 메타태그 제공.

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
