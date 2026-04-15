---
name: cite-post
description: "terry.artlab.ai 포스팅 번호를 책의 인라인 인용과 참고문헌에 추가하는 스킬. '/cite-post', '포스팅 링크 추가', '포스트 번호 매칭', '블로그 레퍼런스 연결' 요청 시 반드시 이 스킬을 사용할 것. 새 포스팅이 추가된 후 책을 업데이트할 때 사용한다."
---

# Cite Post — 포스팅 레퍼런스 매칭 및 추가

terry.artlab.ai의 논문 포스팅 번호(`[#N]`)를 책의 인라인 인용과 참고문헌에 추가한다.

## 사용 예시

```
/cite-post From Human Hands to Robot Hands
/cite-post   (인자 없이 — 현재 프로젝트의 책을 대상으로)
```

## 동작 방식

### Step 1: 포스팅 목록 수집

terry-artlab-homepage 프로젝트에서 전체 포스팅 목록을 읽는다:
- 경로: `/Users/terrytaewoongum/Codes/personal/terry-artlab-homepage/posts/papers/`
- 각 폴더의 `meta.json`에서 `postNumber`, `title`, 슬러그(폴더명) 추출
- URL 패턴: `https://terry.artlab.ai/ko/posts/{slug}`

### Step 2: 책의 참고문헌 파싱

`book/ko/ch*.md`와 `book/en/ch*.md`의 `## 참고문헌` / `## References` 섹션을 파싱하여 모든 인용 논문을 추출한다.

### Step 3: 매칭

각 참고문헌 항목의 제목/저자를 포스팅의 제목/저자와 매칭한다.
매칭 기준:
- 논문 제목의 핵심 키워드 매칭 (예: "EgoMimic", "OSMO", "DexUMI")
- 저자명 + 연도 매칭
- 매칭 실패 시 skip (모든 논문에 포스팅이 있는 것은 아님)

### Step 4: 인라인 인용에 포스팅 번호 추가

매칭된 논문의 인라인 인용 옆에 포스팅 번호를 추가한다:

**변경 전 (마크다운):**
```
ExoStart [Smith et al., 2025]
```

**변경 후 (마크다운):**
```
ExoStart [Smith et al., 2025] [#9](https://terry.artlab.ai/ko/posts/2506-exostart)
```

빌드 시 `[#9](URL)`은 일반 마크다운 링크로 변환된다. `target="_blank"` 처리는 build_site.py에서 수행.

### Step 5: 참고문헌 항목에도 포스팅 번호 추가

참고문헌 번호 리스트에도 포스팅 링크를 추가한다:

**변경 전:**
```
7. Smith et al. (2025). ExoStart: ... *arXiv*. https://arxiv.org/...
```

**변경 후:**
```
7. Smith et al. (2025). ExoStart: ... *arXiv*. https://arxiv.org/... [#9](https://terry.artlab.ai/ko/posts/2506-exostart)
```

### Step 6: 영문 챕터도 동일 처리

`book/en/ch*.md`에도 동일한 매칭과 추가를 수행한다.
영문 URL: `https://terry.artlab.ai/en/posts/{slug}`

### Step 7: 리빌드

`python3 build_site.py`를 실행하여 HTML을 재생성한다.

## 현재 매칭 테이블 (2026-04-07 기준)

이 테이블은 포스팅이 추가될 때마다 업데이트한다.

| 논문 키워드 | 포스트 # | 슬러그 | 책 내 인용 여부 |
|------------|---------|-------|--------------|
| ForceVLA | #1 | 2505-forcevla-force-aware-moe | Ch3 |
| pi0 | #2 | 2410-pi0-vla-flow-model | Ch1, Ch5, Ch7 |
| Park et al. stretchable glove | #6 | 2407-stretchable-glove-hand-pose | Ch2, Ch7 |
| DexUMI | #8 | 2505-dexumi | Ch2 |
| ExoStart | #9 | 2506-exostart | Ch2 |
| DEXOP | #10 | 2509-dexop | Ch1, Ch2, Ch5 |
| UniTacHand | #16 | 2512-unitachand | Ch6 |
| OSMO | #18 | 2512-osmo-tactile-glove | Ch2, Ch3, Ch5, Ch6, Ch7 |
| TacGlove (가상) | #26 | 2610-tactile-stretchable-glove-data-engine | Ch7 |
| TacTeleOp (가상) | - | - | Ch8 |
| TacPlay (가상) | #27 | 2611-tactile-play-cross-embodiment | Ch9 |

## build_site.py 연동

포스팅 링크 `[#N](URL)`은 마크다운 링크로 처리된다.
build_site.py의 `process_inline()`에서 `[#N](URL)` → `<a href="URL" target="_blank" class="post-link">#N</a>`로 변환한다.

## 주의사항

- 인라인 인용의 `[Author, Year]`는 빌드 시 `<sup>` 숫자 링크로 변환되고, 포스팅 `[#N]`은 별도 링크로 남음
- 같은 논문이 여러 챕터에 인용된 경우, 모든 챕터에서 포스팅 번호를 추가
- 포스팅 번호는 terry.artlab.ai의 전역 번호체계를 따름 (논문 #1~#27+)
- 영문 챕터의 포스팅 URL은 `/en/posts/` 사용
