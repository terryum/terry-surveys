# bibtex/ — 통합 BibTeX 관리

모든 서베이가 공유하는 **단일 source of truth**. 각 서베이의 `surveys/<name>/book/references.bib`는 이 마스터의 **부분집합(subset)**으로만 존재한다.

## 파일 구조

- `references.bib` — 마스터 파일 (중복 키 금지, 서베이 간 동일 논문은 반드시 동일 키)
- `README.md` — 본 문서
- `refs_index.py` — 인덱스 빌더 + post↔survey 매칭 도구 (Tier 1 arXiv/DOI/Nature ID exact + Tier 3 fuzzy fallback)
- `add_ref_links.py` — 레거시 ref 링크 삽입 도우미
- `__init__.py` — 패키지 마커 (Python import 용)
- `refs_index.json` — 생성물: 모든 서베이 ref를 파싱해 arXiv/DOI/Nature ID로 인덱싱 (gitignored)
- `posts_index.json` — 생성물: terryum-ai의 포스트 meta.json을 읽어 post↔ID 매핑 (gitignored)

> **설계 원칙**: 참고문헌 관련 모든 파일·도구·생성물은 `bibtex/` 안에서 관리된다. 다른 디렉토리에 ref 관련 코드를 두지 않는다.

## 인덱스 도구 사용법

```bash
# 서베이 ref 인덱스 갱신 (서베이 챕터 수정 후)
python3 bibtex/refs_index.py build

# 홈페이지 포스트 인덱스 갱신 (새 포스트 등록 후)
python3 bibtex/refs_index.py build-posts

# 둘 다
python3 bibtex/refs_index.py build-all

# 특정 포스트 slug가 서베이에서 인용됐는지 찾기 (Tier 1 exact + Tier 3 fuzzy)
python3 bibtex/refs_index.py match 2412-f-tac-hand

# 키워드로 서베이 ref 검색
python3 bibtex/refs_index.py search "pi0"
```

`build.py` 래퍼로도 호출 가능: `python3 build.py --index`, `--match <slug>`, `--search <kw>`.

## 왜 두 파일(마스터 + 서베이별)이 공존하는가

- **빌드 속도/가독성**: `shared/build_site.py`는 서베이별 `.bib`만 읽는다. 로컬 파일은 해당 서베이가 실제 인용하는 엔트리만 유지.
- **Tier 1 매칭**: 포스트↔서베이 연결은 `bibtex/refs_index.py`가 서베이 로컬 `.bib`와 ref 라인에서 arXiv ID / DOI / Nature 아티클 ID를 추출해 exact match로 판정한다. 잘못된 논문에 링크가 붙는 false positive가 차단된다.
- **일관성 보장**: 자매 서베이에서 같은 논문을 다른 키로 중복 작성하지 않도록 마스터에서 먼저 키를 확정.

## 워크플로우 (신규 논문 인용 시 4단계)

```
1. grep 마스터
   grep -i "<title-keyword>\|<arxiv-id>" bibtex/references.bib

2. 있으면 → 그 키를 서베이 로컬 .bib에 복사해 재사용
3. 없으면 → 마스터에 엔트리 추가 → 서베이 로컬에도 복사
4. 자매 서베이가 이미 사용 중이면 → 반드시 동일 키 사용 (새로 만들지 말 것)
```

## 키 네이밍 규약

```
{firstauthorlastname}{year}{keyword}
```

- 전부 소문자, 특수문자 제거 (예: `João Damião Almeida, 2025` → `almeida2025roleoftouch`)
- `keyword`는 논문 약어/핵심어 1개 (예: OSMO→`osmo`, Soft Robotic Hand Tactile Palm-Finger→`soft`)
- 충돌 시 `keyword`를 더 구체적으로 (예: `zhang2025soft` 대신 `zhang2025softpalm`)

## 섹션 마커

```bibtex
% ------ {survey-short}:ChNN / {survey-short}:ChNN ------
```

서베이 약어:
- `snu` = snu-tactile-hand
- `rht` = robot-hand-tactile-sensor
- `vla` = vla-agentic-robotics

여러 서베이가 공유하면 `rht:shared` 식으로 표기.

## 서베이 생성·업데이트 시 체크리스트

신규 서베이(`python3 build.py --new <name>`) 또는 기존 서베이에 새 논문 추가 시 **반드시**:

- [ ] 논문 인용 전에 `bibtex/references.bib` grep
- [ ] 신규 엔트리는 마스터에 먼저 추가 (섹션 코멘트 포함)
- [ ] 자매 서베이의 기존 키와 충돌 없는지 확인
- [ ] 서베이 로컬 `book/references.bib`에 동일 엔트리 복사
- [ ] PR·커밋 메시지에 `bibtex: +<N> entries to master + <survey>` 형태로 명시

## 초기 seeding 이력

- 2026-04-17: 팜 연구 8건 (snu-tactile-hand 통합 작업) — `zhao2025ftac`, `zhang2025soft`, `almeida2025roleoftouch`, `sharma2025sparsh`, `liu2024romeo`, `richardson2025isyhand`, `npj2026activepalm`, `pozzi2024actuatedpalms`
- 2026-04-21: 3서베이 로컬 `.bib` union → 마스터 15 → 244 엔트리 (Phase 1 완료). 도구: `shared/scripts/union_bibtex.py`. 서베이 간 공유 paper 7개는 rht 버전으로 canonical 확정.

## 충돌·TODO

| 키 | 이슈 | 해결 예정 |
|-----|------|-----------|
| ~~`npj2026activepalm`~~ → `zhou2026activepalm` | **2026-04-17 해결**: 저자 Zhou/Lee/Gu/She 확정, 키 재명명 완료 |
| `zhang2025soft` | 네이밍이 제너릭 | 충돌 발생 시 `zhang2025softpalm`으로 재명명 고려 |
