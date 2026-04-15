---
name: link-post-to-surveys
description: "새 논문 포스팅이 홈페이지에 추가된 후, 모든 survey의 참고문헌에서 해당 논문을 찾아 [post] 링크를 추가하는 스킬. '/link-post', 'survey에 포스트 연결', '서베이 포스트 링크' 요청 시 사용. /post 스킬 실행 후 자동으로 호출되어야 함."
---

# Link Post to Surveys — 포스트-서베이 참고문헌 교차 연결

새 논문 포스트가 terry.artlab.ai에 추가되었을 때, terry-surveys 모노레포의 모든 서베이 참고문헌에서 해당 논문을 찾아 `[post]` 링크를 추가한다.

## 사용 예시

```
/link-post-to-surveys 2505-dexumi
/link-post-to-surveys   (인자 없이 — 가장 최근 포스트를 대상으로)
```

## 동작 방식 (경량 Fast Path)

### Step 1: refs_index.json으로 빠른 매칭

**무거운 전체 파일 검색을 하지 않는다.** 대신 사전 빌드된 인덱스를 사용한다:

```bash
cd /Users/terrytaewoongum/Codes/personal/terry-surveys
python3 shared/refs_index.py match <post-slug>
```

이 명령은 포스트 slug의 키워드를 인덱스의 모든 참고문헌과 대조하여 매칭 후보를 score 순으로 반환한다. 수백 개 참고문헌을 밀리초 내에 검색할 수 있다.

### Step 2: 매칭 결과 확인

`match` 결과에서 score가 높은 항목(score >= 3)을 실제 매칭으로 판단한다. 결과에는 각 참고문헌의 위치(survey, chapter, ref_num)가 포함되어 있다.

예시 결과:
```
[score=4] Xu (2025). DexUMI: Using human hand as...
  -> robot-hand-tactile-sensor ch06[6], snu-tactile-hand ch02[6]
```

### Step 3: 해당 챕터 파일에 [post] 링크 추가

매칭된 각 위치(survey/chapter)의 참고문헌 항목에 `[post]` 링크를 추가한다:

**변경 전:**
```
6. Xu et al. (2025). DexUMI: ... *arXiv*. [arXiv](...) [scholar](...)
```

**변경 후:**
```
6. Xu et al. (2025). DexUMI: ... *arXiv*. [arXiv](...) [post](https://terry.artlab.ai/ko/posts/2505-dexumi) [scholar](...)
```

- `book/ko/` 파일: `https://terry.artlab.ai/ko/posts/{slug}`
- `book/en/` 파일: `https://terry.artlab.ai/en/posts/{slug}`

### Step 4: 인라인 인용에도 포스트 링크 추가 (선택적)

참고문헌뿐 아니라 본문의 인라인 인용에도 포스트 링크를 추가할 수 있다:

```
DexUMI [Xu et al., 2025] [#8](https://terry.artlab.ai/ko/posts/2505-dexumi)
```

이 기능은 cite-post 스킬과 동일한 패턴이다.

### Step 5: 인덱스 업데이트

작업 완료 후 인덱스를 갱신한다:
```bash
python3 shared/refs_index.py build
```

### Step 6: 리빌드

변경된 서베이를 리빌드한다:
```bash
python3 build.py <affected-survey-name>
```

## /post 스킬과의 연동

홈페이지나 옵시디언에서 `/post` 스킬로 새 논문을 포스팅할 때, 마지막 단계에서 이 스킬을 호출한다:

```
/post 완료 후 → /link-post-to-surveys <new-slug>
```

### /post 스킬에 추가할 안내문 (terry-artlab-homepage 또는 obsidian의 /post SKILL.md에):
```
## Post-Survey 교차 연결 (Optional)

새 논문 포스트를 작성한 후, terry-surveys 모노레포에서 해당 논문이 
서베이 참고문헌에 인용되어 있는지 확인할 수 있다:

cd /Users/terrytaewoongum/Codes/personal/terry-surveys
python3 shared/refs_index.py match <new-post-slug>

매칭 결과가 있으면 /link-post-to-surveys <slug> 를 실행하여 
서베이 참고문헌에 [post] 링크를 자동 추가한다.
```

## 반대 방향: 새 서베이 작성 시 기존 포스트 매칭

새 서베이를 작성할 때, 기존 포스트가 참고문헌에 이미 인용되어 있는지 확인하려면:

```bash
# 인덱스 재빌드 (새 서베이 포함)
python3 shared/refs_index.py build

# 각 포스트 slug로 매칭 검색
for slug in $(ls /Users/terrytaewoongum/Codes/personal/terry-artlab-homepage/posts/papers/); do
  python3 shared/refs_index.py match "$slug" 2>/dev/null | head -3
done
```

또는 cite-post 스킬을 직접 사용하면 된다.

## 주의사항

- `refs_index.json`은 참고문헌이 변경될 때마다 `python3 shared/refs_index.py build`로 재빌드 필요
- 포스트 링크가 이미 있는 참고문헌에는 중복 추가하지 않음
- `[post]` 링크는 `[arXiv]`와 `[scholar]` 사이에 배치
