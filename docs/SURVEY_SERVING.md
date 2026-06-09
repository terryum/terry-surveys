# Survey serving — operations checklist

terry-surveys 는 Cloudflare Pages 에 정적 사이트로 배포되고, terryum.ai 의 survey
상세 페이지는 그 정적 사이트를 `ProjectEmbed.tsx` iframe 으로 임베드한다. 이 문서는
서빙·캐시·접근 제어·KG 동기화 관련 운영 작업의 체크리스트다.

문서화된 작업만 정리한다 — Cloudflare Dashboard/API 자동화 코드는 의도적으로 두지
않았다. 운영자가 수동으로 적용한다.

---

## 1. 정적자산 캐시 헤더

`shared/build_site.py` 의 `write_headers()` 가 매 빌드마다 `docs/_headers` 를
다음 내용으로 작성한다:

```
/*.html       → no-cache (max-age=0, must-revalidate)
/css/*        → 1h (max-age=3600)
/js/*         → 1h (max-age=3600)
/assets/*     → 24h (max-age=86400)
```

CSS/JS 가 hash-suffixed filename 이 아니라 보수적으로 1h. assets/ 는 figure swap
이 잦지 않으므로 24h. HTML 은 chapter 수정 즉시 반영되도록 no-cache.

### 검증

```sh
python3 build.py <survey-name>
cat surveys/<survey-name>/docs/_headers
# 위 4개 블록이 보여야 함
```

배포 후 응답 헤더 확인:

```sh
curl -sI https://<project>.pages.dev/css/style.css | grep -i cache-control
# expected: Cache-Control: public, max-age=3600
```

---

## 2. 이미지 경량화 (opt-in)

Gemini 3 Pro Image 가 항상 2K PNG (2–3MB/장) 로 반환하므로, 그림 많은 survey 는
산출물이 100MB 를 넘는다. 기본 빌드는 원본 PNG 를 그대로 두고, 큰 산출물을
줄이고 싶을 때만 별도 스크립트를 실행한다.

```sh
# 변환 미리보기
python3 scripts/optimize-figures.py --dry-run <survey-name>

# 산출물 옆에 .webp + .jpg 생성 (원본 PNG 보존, HTML 참조 미변경)
python3 scripts/optimize-figures.py <survey-name>

# 가장 직접적: PNG 를 JPEG 으로 in-place 교체 + HTML 의 .png 참조도 .jpg 로 치환
python3 scripts/optimize-figures.py --inplace-jpeg <survey-name>
```

원본 `surveys/<name>/assets/figures/` 는 **절대 수정되지 않는다**. 다음 빌드가
다시 원본 PNG 를 docs/ 로 복사하므로, 큰 survey 는 빌드 직후 매번 재실행해야 한다.

### 일반 워크플로

```sh
python3 build.py <survey-name>
python3 scripts/optimize-figures.py --inplace-jpeg <survey-name>
cd surveys/<survey-name>
bash scripts/push.sh "compress figures"
```

### 적용 우선순위

1차 적용 검증 대상: `microbiome-cosmetics-ai` (112MB → 30-40MB 예상).
검수 후 확장: `humanoid-revolution`, `robot-hand-tactile-sensor`, `claude-to-codex`.

---

## 3. group/private survey 의 raw URL 보호

### 문제

terryum.ai 의 `/<lang>/surveys/<slug>` 페이지는 `requireReadAccess` 로
ACL gate 가 걸려 있다. 하지만 iframe 의 `src` 가 가리키는 raw
`https://<project>.pages.dev/...` 는 별도 보호가 없어서, embed_url 만 알면
브라우저로 직접 열 수 있다 (200 응답).

### 보호 대상 (`surveys.json` 의 visibility != "public")

- `survey-snu-largescale-tactile-hand.pages.dev` (visibility: group, allowed_groups: snu)
- `physical-ai-manufacturing.pages.dev` (visibility: group, allowed_groups: snu)

public 서베이는 누구나 볼 수 있어 보호 불필요.

### Cloudflare Access 적용 단계 가이드 (수동, 서베이당 1회)

전제: 사용자가 해당 Pages project 의 owner Cloudflare 계정에 로그인 가능.
Cloudflare Access 의 Zero Trust Free plan 으로 50 user 까지 무료.

#### 단계 1 — Zero Trust 활성화 (최초 1회)

1. https://dash.cloudflare.com 로그인
2. 좌측 메뉴 **Zero Trust** 클릭
3. 처음이면 Team name 설정 (예: `terryum`). 이메일 인증 한 번.
4. 이후 작업 URL: https://one.dash.cloudflare.com/

#### 단계 2 — Access Application 등록 (보호 대상 서베이마다 반복)

1. 좌측 **Access → Applications → Add an application**
2. **Self-hosted** 선택
3. 설정:
   - **Application name**: `Survey - SNU Tactile Hand` (보기용)
   - **Session duration**: `24h` (또는 더 길게 — 사용자가 자주 재인증하지 않도록)
   - **Application domain**: `survey-snu-largescale-tactile-hand.pages.dev` (path 비워두면 사이트 전체 보호)
4. **Identity provider**: 기본 활성화된 "One-time PIN" 유지 (이메일로 6자리 코드 발송).
   Google/GitHub OAuth 도 추가 가능하나 OTP 만으로 충분.

#### 단계 3 — Access Policy 설정

1. 같은 application 의 **Policies** 탭 → **Add a policy**
2. **Policy name**: `SNU members only`
3. **Action**: **Allow**
4. **Rules → Include**:
   - **Emails ending in** 선택 → `@snu.ac.kr` 입력
   - 추가로 본인 이메일 (`terry.t.um@gmail.com`) 도 명시적으로 추가 — 도메인 외 운영자 접근용
5. **Save**

#### 단계 4 — iframe 호환성 확인

terryum.ai 의 group survey 페이지를 열면 iframe 안에서 Cloudflare Access
로그인 화면이 표시된다. 사용자가 이메일 입력 → PIN 받아 인증 → 24h 세션
쿠키 발급 후 iframe 정상 로드. 한 번 인증하면 이후 방문 시 그대로 보임.

iframe 안 로그인 페이지가 깨지면 (X-Frame-Options 충돌), Application
설정에서 다음을 확인:
- Cloudflare Zero Trust → Settings → Authentication → **CORS 및 iframe 허용** 체크
- Application 자체 설정에서 `Allow request to display in iframe` 활성화 (plan 에 따라 존재)

#### 단계 5 — 검증

```sh
# 비인증 상태에서 raw URL 직접 접근 → 302 redirect 또는 401 가 떨어져야 함
curl -sI https://survey-snu-largescale-tactile-hand.pages.dev/ | head -10
# 기대: Cloudflare Access 로그인 페이지로 redirect 또는 access-denied
```

브라우저 시크릿 모드로 위 URL 방문 → 로그인 화면이 보이면 성공.

#### `physical-ai-manufacturing` 도 같은 절차 반복

단계 2-3 만 `physical-ai-manufacturing.pages.dev` 도메인으로 한 번 더.

#### 체크리스트

- [ ] `survey-snu-largescale-tactile-hand.pages.dev` 에 Access policy 적용
- [ ] `physical-ai-manufacturing.pages.dev` 에 Access policy 적용
- [ ] 시크릿 브라우저로 두 URL 직접 방문 — 로그인 페이지 나오는지 확인
- [ ] terryum.ai 의 해당 survey 페이지 방문 — iframe 안 로그인 후 정상 표시 확인

### 알려진 한계

- terryum.ai 의 "group" ACL (Supabase) 와 Cloudflare Access 의 허용 이메일
  리스트는 **자동 동기화되지 않는다**. 양쪽 다 수동 관리. 인원이 적을 때는 OK.
- 사용자 첫 방문 시 iframe 안에서 PIN 인증 필요 — UX 한 번 불편. 이후 24h
  세션 쿠키로 무인증 통과.
- 더 강한 보호 필요 시 Service Token + terryum.ai 서버 프록시 옵션 있으나
  Next.js wrapper 코드 수정 (이번 범위 외).

---

## 4. KG candidate_index 정기 동기화

terry-papers/knowledge-index.json 의 `candidate_index` 섹션은 surveys 의
reference 목록을 후보 paper pool 로 변환한 것이다. 새 survey 가 추가/업데이트
되면 재생성해야 한다.

### 점검 명령

```sh
jq '.candidate_index | {
  generated_at,
  total_candidates,
  surveys: (.by_survey | keys)
}' /Users/terrytaewoongum/Codes/personal/terry-papers/knowledge-index.json
```

`generated_at` 이 최근이고 `surveys` 배열에 `terry-surveys/surveys/` 의 모든
디렉토리가 포함되어 있어야 한다.

### 재실행

```sh
cd /Users/terrytaewoongum/Codes/personal/terryum-ai
node scripts/sync-survey-candidates.mjs

cd /Users/terrytaewoongum/Codes/personal/terry-papers
git status   # knowledge-index.json 변경 확인
git diff --stat
git add knowledge-index.json
git commit -m "chore(kg): refresh candidate_index from terry-surveys"
```

임베딩까지 새로 만들고 싶으면 `--with-embeddings` 추가 (OpenAI API 키 필요).
일반적 refresh 는 임베딩 없이 충분.

### 트리거 시점

- 새 survey 가 deploy 된 직후 (예: `bash scripts/push.sh` 끝나고)
- `terry-surveys/bibtex/refs_index.json` 가 갱신된 후
- 또는 주 1회 정기

### 최근 sync 결과 (2026-05-14)

`generated_at: 2026-05-14T02:32:15Z`, total_candidates 486.
by_survey 6개 포함: claude-to-codex(4), humanoid-revolution(160),
physical-ai-manufacturing(56), robot-hand-tactile-sensor(208),
snu-tactile-hand(87), vla-agentic-robotics(37).

`microbiome-cosmetics-ai` 는 by_survey 에 등장하지 않음. 원인은 refs_index 의
ref 가 1개뿐이고 metadata 가 비어 sync 필터가 candidate 로 채택하지 않기
때문. 해결은 sync 가 아니라 refs 추출:

```sh
python3 build.py --refresh-refs microbiome-cosmetics-ai
python3 build.py --index   # refs_index.json 갱신
cd /Users/terrytaewoongum/Codes/personal/terryum-ai
node scripts/sync-survey-candidates.mjs
```

`claude-to-codex` 도 158 ref 대비 4 candidate 만 등록됨. 이는 filter
(arxiv/doi/nature ID 없는 ref 는 candidate 에서 제외) 결과로 보이며,
필요하면 별도 점검.
