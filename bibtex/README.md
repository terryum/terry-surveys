# bibtex/ — 통합 BibTeX 관리

모든 서베이가 공유하는 **단일 source of truth**. 각 서베이의 `surveys/<name>/book/references.bib`는 이 마스터의 **부분집합(subset)**으로만 존재한다.

## 파일 구조

- `references.bib` — 마스터 파일 (중복 키 금지, 서베이 간 동일 논문은 반드시 동일 키)
- `README.md` — 본 문서

## 왜 두 파일(마스터 + 서베이별)이 공존하는가

- **빌드 속도/가독성**: `shared/build_site.py`는 서베이별 `.bib`만 읽는다. 로컬 파일은 해당 서베이가 실제 인용하는 엔트리만 유지.
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
- TODO: 3개 서베이 기존 엔트리의 union·dedupe 1회성 작업 (후속 PR)

## 충돌·TODO

| 키 | 이슈 | 해결 예정 |
|-----|------|-----------|
| `npj2026activepalm` | 첫 저자 미확인 (nature.com fetch 차단) | PDF 확인 후 `{surname}2026activepalm`으로 재명명 |
| `zhang2025soft` | 네이밍이 제너릭 | 충돌 발생 시 `zhang2025softpalm`으로 재명명 고려 |
