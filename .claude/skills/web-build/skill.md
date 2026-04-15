---
name: web-build
description: "완성된 책 마크다운을 기반으로 revfactory.github.io/ai-trend-onboarding/ 스타일의 정적 웹사이트를 구축하는 스킬. 다크 모드, glassmorphism 카드, GSAP 스크롤 애니메이션, 파티클 배경이 있는 기술 서적 웹 뷰어를 HTML/CSS/JS만으로 생성한다. 웹페이지 생성, 사이트 빌드, GitHub Pages 배포, 책의 웹 버전 제작이 필요할 때 이 스킬을 사용할 것."
---

# Web Build Skill

책 마크다운 원고를 정적 웹사이트로 변환한다. 참조 사이트(revfactory)의 디자인 언어를 충실히 재현한다.

## 참조 사이트 분석 결과

- **기술**: 순수 HTML/CSS/JS, 프레임워크 없음
- **호스팅**: GitHub Pages
- **디자인**: 다크 모드 전용, glassmorphism, 파티클 배경
- **애니메이션**: GSAP + ScrollTrigger
- **폰트**: Noto Sans KR (Google Fonts)
- **구조**: index.html(랜딩) + ch{N}.html(챕터별)

## 워크플로우

### Step 1: 사이트 구조 생성

```
docs/
├── index.html              # 랜딩 페이지 (히어로 + 목차 그리드)
├── ch01.html ~ ch12.html   # 챕터 페이지
├── references.html          # 참고문헌
├── glossary.html            # 용어집
├── css/
│   └── style.css           # 전역 스타일
├── js/
│   ├── main.js             # 파티클 배경, 공통 네비게이션
│   └── chapter.js          # GSAP 스크롤 애니메이션
└── assets/
    ├── figures/             # 챕터 내 그림들
    └── icons/               # 네비게이션 아이콘
```

### Step 2: 랜딩 페이지 (index.html)

구성 요소:
1. **히어로 섹션**: 책 제목 + 부제 + 그라디언트 텍스트
2. **소개 섹션**: 3개의 glassmorphism 카드 ("왜 촉각인가", "이 책의 특징", "대상 독자")
3. **Part별 챕터 그리드**: 4개 Part × 3 챕터, Part별 악센트 색상 구분

```html
<!-- 히어로 -->
<section class="hero">
  <canvas id="particle-canvas"></canvas>
  <h1 class="gradient-text">Tactile Sensing for Robot Hands</h1>
  <p class="subtitle">촉각 센서부터 지능형 조작까지</p>
</section>

<!-- 챕터 그리드 -->
<section class="chapters">
  <div class="part-group" data-accent="teal">
    <h2>Part I: Foundations</h2>
    <div class="chapter-grid">
      <a href="ch01.html" class="chapter-card">
        <span class="ch-num">01</span>
        <h3>왜 촉각인가</h3>
        <p>로봇 조작의 미래</p>
        <span class="arrow">→</span>
      </a>
      ...
    </div>
  </div>
</section>
```

### Step 3: 챕터 페이지 (ch{NN}.html)

구성 요소:
1. **좌측 사이드바**: 섹션별 dot 네비게이션 (스크롤 위치 연동)
2. **본문 영역**: 마크다운 → HTML 변환된 콘텐츠
3. **하단 네비게이션**: 이전/다음 챕터 이동

```html
<nav class="sidebar-nav">
  <div class="nav-dot active" data-section="sec-1">
    <span class="dot"></span>
    <span class="label">N.1 섹션명</span>
  </div>
  ...
</nav>

<main class="chapter-content">
  <header class="chapter-header">
    <span class="part-label">Part I: Foundations</span>
    <h1>Chapter 1: 왜 촉각인가</h1>
    <p class="chapter-summary">...</p>
  </header>

  <section id="sec-1" class="content-section">
    <h2>1.1 로봇 조작의 현재와 한계</h2>
    ...
  </section>
</main>

<nav class="chapter-nav">
  <a href="ch00.html" class="prev">← 이전</a>
  <a href="ch02.html" class="next">다음 →</a>
</nav>
```

### Step 4: CSS 스타일링

상세 CSS 사양은 `references/style-spec.md`를 참조한다.

핵심 스타일 변수:

```css
:root {
  --bg-primary: #0a0a0f;
  --bg-card: rgba(255,255,255,0.03);
  --text-primary: #e0e0e0;
  --text-secondary: #a0a0a0;
  --border-subtle: rgba(255,255,255,0.08);
  --accent-part1: #00D4AA;  /* teal */
  --accent-part2: #3498DB;  /* blue */
  --accent-part3: #9B59B6;  /* purple */
  --accent-part4: #FF6B35;  /* orange */
  --font-family: 'Noto Sans KR', sans-serif;
  --radius-card: 16px;
}
```

### Step 5: JavaScript 기능

**main.js:**
- Canvas 파티클 배경 (60개 노드 + 연결선)
- 챕터 카드 hover 효과
- 스무스 스크롤

**chapter.js:**
- GSAP ScrollTrigger 기반 섹션 진입 애니메이션
- 사이드바 dot 활성 상태 업데이트
- 인용 논문 클릭 → references.html 해당 항목으로 이동

### Step 6: 마크다운 → HTML 변환

book/ 디렉토리의 마크다운 파일을 HTML로 변환한다. 변환 규칙:

| 마크다운 | HTML |
|---------|------|
| `# Chapter N: 제목` | `<h1>` (챕터 헤더) |
| `## N.X 섹션` | `<section id="sec-X"><h2>` |
| `### N.X.Y 하위` | `<h3>` |
| `> **핵심 연구**: ...` | `<blockquote class="key-paper">` |
| `[📊 Figure N.X: ...]` | `<figure><img><figcaption>` |
| `$$수식$$` | KaTeX 렌더링 또는 이미지 |
| 표 | `<table class="styled-table">` |
| 코드 블록 | `<pre><code class="language-python">` |

### Step 7: 빌드 및 검증

1. 모든 HTML 파일 생성 후 내부 링크 유효성 검증
2. 로컬 서버로 시각적 확인 가능하도록 안내
3. GitHub Pages 배포 설정 (docs/ 디렉토리 기반)

## 품질 기준

- 모든 페이지가 W3C HTML5 유효성 통과
- 모바일(375px), 태블릿(768px), 데스크탑(1200px) 3가지 뷰포트 대응
- 파티클 애니메이션이 성능 저하 없이 60fps 유지
- 모든 내부 링크 유효
