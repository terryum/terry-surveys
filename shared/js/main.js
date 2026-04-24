/* ============================================
   From Human Hands to Robot Hands — Main JS
   Particle background, navigation, language toggle
   ============================================ */

// --- Particle Background ---
(function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const PARTICLE_COUNT = 60;
  const CONNECTION_DISTANCE = 150;
  let particles = [];
  let animationId;
  let w, h;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }

  function createParticles() {
    particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        r: Math.random() * 2 + 1
      });
    }
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);

    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < CONNECTION_DISTANCE) {
          const alpha = (1 - dist / CONNECTION_DISTANCE) * 0.15;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(155, 89, 182, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    // Draw particles
    for (const p of particles) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(155, 89, 182, 0.5)';
      ctx.fill();
    }
  }

  function update() {
    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0 || p.x > w) p.vx *= -1;
      if (p.y < 0 || p.y > h) p.vy *= -1;
    }
  }

  function animate() {
    update();
    draw();
    animationId = requestAnimationFrame(animate);
  }

  resize();
  createParticles();
  animate();

  window.addEventListener('resize', () => {
    resize();
    createParticles();
  });
})();

// --- Language Toggle ---
(function initLangToggle() {
  const currentPath = window.location.pathname;
  const langKey = 'preferred-lang';

  // Save preference when visiting a language page
  if (currentPath.includes('/ko/')) {
    localStorage.setItem(langKey, 'ko');
  } else if (currentPath.includes('/en/')) {
    localStorage.setItem(langKey, 'en');
  }
})();

// --- Smooth Scroll for Anchors ---
document.addEventListener('click', function(e) {
  const anchor = e.target.closest('a[href^="#"]');
  if (!anchor) return;
  // Skip cite-links — handled by chapter.js with highlight + back-link
  if (anchor.classList.contains('cite-link') || anchor.classList.contains('cite-backlink')) return;
  const targetId = anchor.getAttribute('href').slice(1);
  const target = document.getElementById(targetId);
  if (target) {
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});

// --- Fade-in on scroll (fallback if GSAP not loaded) ---
(function initFadeIn() {
  if (typeof gsap !== 'undefined') return; // GSAP will handle it

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    },
    { threshold: 0.1 }
  );

  document.querySelectorAll('.content-section, .fade-in, .chapter-card, .intro-card').forEach(el => {
    observer.observe(el);
  });
})();

// --- Embed bridge: sync iframe location to parent URL ---
// Runs only when embedded. Parent reflects current chapter + scroll in query params
// so language toggle (which preserves query params) lands on the same spot.
(function embedBridge() {
  var inIframe = false;
  try { inIframe = window.self !== window.top; } catch (e) { inIframe = true; }
  if (!inIframe) return;

  function currentChapter() {
    var path = window.location.pathname;
    var m = path.match(/\/(?:ko|en)\/([^\/]*)$/);
    if (!m) return '';
    var file = m[1];
    if (!file || file === 'index.html') return '';
    return file;
  }

  function postLocation() {
    try {
      window.parent.postMessage({
        type: 'survey_location',
        chapter: currentChapter(),
        scrollY: Math.round(window.scrollY || window.pageYOffset || 0)
      }, '*');
    } catch (e) { /* noop */ }
  }

  // Initial announcements (covers DOM ready, after images/layout settle)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', postLocation);
  } else {
    postLocation();
  }
  window.addEventListener('load', postLocation);

  // Throttled scroll updates
  var scrollTimer = null;
  window.addEventListener('scroll', function () {
    if (scrollTimer) return;
    scrollTimer = setTimeout(function () {
      scrollTimer = null;
      postLocation();
    }, 150);
  }, { passive: true });

  // Parent → iframe: restore scroll after language switch
  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'restore_scroll') return;
    var y = Number(e.data.scrollY) || 0;
    if (y <= 0) return;
    // Retry across layout shifts from image loading / GSAP
    window.scrollTo(0, y);
    setTimeout(function () { window.scrollTo(0, y); }, 100);
    setTimeout(function () { window.scrollTo(0, y); }, 500);
    setTimeout(function () { window.scrollTo(0, y); }, 1200);
  });
})();
