# Web Build Style Specification

revfactory.github.io/ai-trend-onboarding/ 스타일을 기반으로 한 상세 CSS/JS 사양.

---

## 목차
1. [색상 시스템](#1-색상-시스템)
2. [타이포그래피](#2-타이포그래피)
3. [레이아웃](#3-레이아웃)
4. [컴포넌트](#4-컴포넌트)
5. [애니메이션](#5-애니메이션)
6. [반응형](#6-반응형)

---

## 1. 색상 시스템

### 배경

```css
body {
  background: #0a0a0f;
}

/* 라디언트 오버레이 */
body::before {
  content: '';
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(155, 89, 182, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, rgba(52, 152, 219, 0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, rgba(0, 212, 170, 0.05) 0%, transparent 50%);
  pointer-events: none;
  z-index: 0;
}
```

### Part별 악센트 그라디언트

```css
.part-1 { --accent: #00D4AA; --accent-glow: rgba(0, 212, 170, 0.15); }
.part-2 { --accent: #3498DB; --accent-glow: rgba(52, 152, 219, 0.15); }
.part-3 { --accent: #9B59B6; --accent-glow: rgba(155, 89, 182, 0.15); }
.part-4 { --accent: #FF6B35; --accent-glow: rgba(255, 107, 53, 0.15); }
```

### 히어로 제목 그라디언트

```css
.gradient-text {
  background: linear-gradient(135deg, #00D4AA, #3498DB, #9B59B6, #E8396B, #FF6B35);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

## 2. 타이포그래피

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

body { font-family: 'Noto Sans KR', sans-serif; font-weight: 400; color: #e0e0e0; }
h1 { font-size: clamp(2rem, 5vw, 4rem); font-weight: 900; }
h2 { font-size: clamp(1.5rem, 3vw, 2.5rem); font-weight: 700; }
h3 { font-size: clamp(1.2rem, 2vw, 1.8rem); font-weight: 500; }
p { font-size: clamp(0.95rem, 1.2vw, 1.1rem); line-height: 1.8; color: #a0a0a0; }
```

## 3. 레이아웃

### 랜딩 페이지

```
┌──────────────────────────────────────────┐
│              [파티클 캔버스]               │
│                                          │
│     Tactile Sensing for Robot Hands      │  히어로
│         촉각 센서부터 지능형 조작까지        │
│                                          │
├──────────────────────────────────────────┤
│  [카드1]    [카드2]    [카드3]             │  소개 섹션
├──────────────────────────────────────────┤
│  Part I: Foundations                     │
│  [Ch1]  [Ch2]  [Ch3]                    │  챕터 그리드
├──────────────────────────────────────────┤
│  Part II: Sensing & Data                 │
│  [Ch4]  [Ch5]  [Ch6]                    │
├──────────────────────────────────────────┤
│  ...                                     │
└──────────────────────────────────────────┘
```

### 챕터 페이지

```
┌────┬──────────────────────────────────────┐
│ ●  │  Part I: Foundations                 │
│ ●  │  Chapter 1: 왜 촉각인가              │  헤더
│ ●  │                                      │
│ ●  │  1.1 로봇 조작의 현재와 한계          │
│    │  [본문 콘텐츠]                        │  섹션
│    │                                      │
│    │  1.2 촉각의 역할                      │
│    │  [본문 콘텐츠]                        │  섹션
│    │                                      │
│    │  ← 이전          다음 →              │  네비게이션
└────┴──────────────────────────────────────┘
  좌측
  사이드바
```

## 4. 컴포넌트

### 챕터 카드

```css
.chapter-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 2rem;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.chapter-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--accent);
  opacity: 0;
  transition: opacity 0.3s;
}

.chapter-card:hover {
  transform: translateY(-6px);
  border-color: var(--accent);
  box-shadow: 0 12px 40px var(--accent-glow);
}

.chapter-card:hover::before { opacity: 1; }
```

### 핵심 논문 인용 블록

```css
.key-paper {
  background: rgba(52, 152, 219, 0.08);
  border-left: 3px solid var(--accent);
  padding: 1rem 1.5rem;
  border-radius: 0 12px 12px 0;
  margin: 1.5rem 0;
}
```

### 사이드바 네비게이션

```css
.sidebar-nav {
  position: fixed;
  left: 2rem;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  z-index: 100;
}

.nav-dot {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
}

.nav-dot .dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  transition: all 0.3s;
}

.nav-dot.active .dot {
  background: var(--accent);
  box-shadow: 0 0 10px var(--accent-glow);
}

.nav-dot .label {
  font-size: 0.8rem;
  color: #666;
  opacity: 0;
  transition: opacity 0.3s;
}

.sidebar-nav:hover .label { opacity: 1; }
```

## 5. 애니메이션

### 파티클 배경 (Canvas)

```javascript
// 60개 노드, 연결 거리 150px
const PARTICLE_COUNT = 60;
const CONNECTION_DISTANCE = 150;
const PARTICLE_COLOR = 'rgba(155, 89, 182, 0.5)'; // purple
const LINE_COLOR = 'rgba(155, 89, 182, 0.15)';
```

### GSAP ScrollTrigger (챕터 페이지)

```javascript
// 섹션 진입 애니메이션
gsap.from('.content-section', {
  scrollTrigger: {
    trigger: '.content-section',
    start: 'top 80%',
    toggleActions: 'play none none reverse'
  },
  y: 40,
  opacity: 0,
  duration: 0.8,
  stagger: 0.15
});
```

## 6. 반응형

```css
/* 태블릿 */
@media (max-width: 768px) {
  .chapter-grid { grid-template-columns: 1fr; }
  .sidebar-nav { display: none; }
  .chapter-content { margin-left: 0; padding: 1rem; }
}

/* 모바일 */
@media (max-width: 480px) {
  h1 { font-size: 1.8rem; }
  .chapter-card { padding: 1.2rem; }
}
```
