---
name: critical-analysis
description: "Agentic Coding과 Agentic Robotics의 근본적 차이를 7대 차원으로 분석하고, 연구 흐름의 패러다임 전환을 포착하는 스킬. 'gap 분석', '차이 분석', '흐름 비교', 'agentic coding vs robotics' 요청 시 사용."
---

# Critical Analysis — Agentic Coding vs Agentic Robotics

이 책의 핵심 관점인 "Agentic Coding과 Agentic Robotics의 대비"를 체계적으로 분석한다.

## 분석 프레임워크: 7대 차원

### 1. Error Feedback Loop
| Agentic Coding | Agentic Robotics |
|---------------|-----------------|
| Stack trace — 정확한 에러 위치와 원인 | 센서 노이즈 — 실패 원인 모호 |
| 즉시 피드백 | 지연된, 불완전한 피드백 |
| 예: pytest 실패 메시지 | 예: gripper slip 감지 → 왜 미끄러졌는지 불명확 |

**분석할 논문**: REFLECT (failure explanation), VeriGraph (execution verification)

### 2. Execution Determinism
| Agentic Coding | Agentic Robotics |
|---------------|-----------------|
| 동일 코드 → 동일 결과 | 동일 명령 → 다른 결과 (마찰, 물체 위치 변동) |
| 환경 통제 가능 | 환경 변동이 불가피 |

**분석할 논문**: Diffusion Policy (확률적 정책), DROID (다양한 환경)

### 3. State Representation
| Agentic Coding | Agentic Robotics |
|---------------|-----------------|
| 코드, 파일 시스템, 스크린샷 | Scene graph, point cloud, tactile sensor |
| 완전 관측 가능 | 부분 관측 (occluded objects) |

**분석할 논문**: SayPlan (3D scene graph), RoboEXP (action-conditioned scene graph)

### 4. Memory Architecture
| Agentic Coding | Agentic Robotics |
|---------------|-----------------|
| 긴 컨텍스트 윈도우, 파일 영구 저장 | 실시간 공간 메모리, 제한된 처리 시간 |
| 과거 코드 히스토리 쉽게 조회 | 과거 경험을 효율적으로 요약/저장해야 |

**분석할 논문**: KARMA (long/short-term memory), Embodied-RAG

### 5. Action Space
| Agentic Coding | Agentic Robotics |
|---------------|-----------------|
| 이산 (API 호출, 파일 편집) | 연속 (관절 토크, 그리퍼 힘) |
| 명확한 action boundary | action 경계가 모호 (언제 "완료"인가?) |

**분석할 논문**: RT-H (language-conditioned hierarchy), HAMSTER (coarse→precise)

### 6. Verification & Testing
| Agentic Coding | Agentic Robotics |
|---------------|-----------------|
| Unit test, CI/CD — 빠르고 저렴 | Physical trial — 느리고 비쌈 |
| Simulation ≈ production | Sim2Real gap |

**분석할 논문**: SIMPLER (sim evaluation), Natural Language Sim2Real

### 7. Recoverability
| Agentic Coding | Agentic Robotics |
|---------------|-----------------|
| git revert, undo — 완전 복구 | 물리적 행동은 되돌릴 수 없음 |
| 실험적 시도의 비용이 낮음 | 실패 비용이 높음 (파손, 안전) |

**분석할 논문**: AutoRT (safety constraints), BUMBLE (building-wide recovery)

## 패러다임 전환 분석 형식

```markdown
## [전환 이름] (연도)
- **이전 패러다임**: ...
- **전환 계기**: 어떤 논문/기술이 이 전환을 이끌었는가
- **새 패러다임**: ...
- **Agentic Coding 대응**: 디지털 에이전트에서 유사한 전환이 있었는가
- **남은 Gap**: 이 전환이 해소하지 못한 문제
```

## 출력
4개 분석 파일을 `_workspace/02_analyst_*.md`에 저장한다:
1. `02_analyst_gap_analysis.md` — 7대 차원 심층 비교
2. `02_analyst_paradigm_shifts.md` — 패러다임 전환 타임라인
3. `02_analyst_open_problems.md` — 미해결 문제와 연구 방향
4. `02_analyst_paper_connections.md` — 논문 간 영향 관계 맵
