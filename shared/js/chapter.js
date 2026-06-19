/* ============================================
   From Human Hands to Robot Hands — Chapter JS
   GSAP ScrollTrigger animations, sidebar nav
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {

  // --- GSAP ScrollTrigger Animations ---
  if (typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);

    // Section enter animations
    gsap.utils.toArray('.content-section').forEach((section, i) => {
      gsap.from(section, {
        scrollTrigger: {
          trigger: section,
          start: 'top 85%',
          toggleActions: 'play none none reverse'
        },
        y: 40,
        opacity: 0,
        duration: 0.8,
        delay: i * 0.05
      });
    });

    // Chapter header animation
    const header = document.querySelector('.chapter-header');
    if (header) {
      gsap.from(header, {
        y: 30,
        opacity: 0,
        duration: 1,
        ease: 'power2.out'
      });
    }

    // Figure animations
    gsap.utils.toArray('figure').forEach(fig => {
      gsap.from(fig, {
        scrollTrigger: {
          trigger: fig,
          start: 'top 85%',
          toggleActions: 'play none none reverse'
        },
        y: 30,
        opacity: 0,
        duration: 0.6
      });
    });

    // Table animations
    gsap.utils.toArray('.styled-table').forEach(table => {
      gsap.from(table, {
        scrollTrigger: {
          trigger: table,
          start: 'top 85%',
          toggleActions: 'play none none reverse'
        },
        y: 20,
        opacity: 0,
        duration: 0.6
      });
    });
  } else {
    // Fallback: just make everything visible
    document.querySelectorAll('.content-section').forEach(el => {
      el.classList.add('visible');
    });
  }

  // --- Sidebar Dot Navigation ---
  const sidebarNav = document.querySelector('.sidebar-nav');
  const sections = document.querySelectorAll('.content-section[id]');

  if (sidebarNav && sections.length > 0) {
    // Update active dot on scroll
    const observerOptions = {
      rootMargin: '-20% 0px -70% 0px',
      threshold: 0
    };

    const sectionObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          document.querySelectorAll('.sidebar-nav .nav-dot').forEach(dot => {
            dot.classList.toggle('active', dot.getAttribute('data-section') === id);
          });
        }
      });
    }, observerOptions);

    sections.forEach(section => sectionObserver.observe(section));

    // Click to scroll
    sidebarNav.querySelectorAll('.nav-dot').forEach(dot => {
      dot.addEventListener('click', () => {
        const targetId = dot.getAttribute('data-section');
        const target = document.getElementById(targetId);
        if (target) {
          const headerOffset = 100;
          const y = target.getBoundingClientRect().top + window.pageYOffset - headerOffset;
          window.scrollTo({ top: y, behavior: 'smooth' });
        }
      });
    });
  }

  // --- Citation click: scroll reference to top with offset ---
  function scrollToWithOffset(el, offset) {
    const y = el.getBoundingClientRect().top + window.pageYOffset - offset;
    window.scrollTo({ top: y, behavior: 'smooth' });
    // Re-adjust after layout settles (images loading can shift positions)
    setTimeout(function() {
      const y2 = el.getBoundingClientRect().top + window.pageYOffset - offset;
      if (Math.abs(y2 - window.pageYOffset) > 5) {
        window.scrollTo({ top: y2, behavior: 'smooth' });
      }
    }, 600);
  }

  document.querySelectorAll('a.cite-link').forEach((link, idx) => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      const targetId = this.getAttribute('href').substring(1);
      const target = document.getElementById(targetId);
      if (!target) return;

      // Use the build-time citation id when available. Older generated pages
      // get a deterministic fallback so every click can become the back target.
      const citeSup = this.closest('sup');
      if (!citeSup) return;
      if (!citeSup.id) {
        citeSup.id = 'cite-back-' + targetId + '-' + idx;
      }
      const backId = citeSup.id;

      // Scroll reference into view with padding at top
      const headerOffset = 100;
      scrollToWithOffset(target, headerOffset);

      // Highlight the reference
      target.classList.add('ref-highlight');
      setTimeout(() => target.classList.remove('ref-highlight'), 3000);

      // The same reference can be cited from several places. Always retarget
      // the backlink to the most recently clicked citation.
      let backLink = target.querySelector('.cite-backlink');
      if (!backLink) {
        backLink = document.createElement('a');
        backLink.className = 'cite-backlink';
        backLink.textContent = ' [본문으로 돌아가기]';
        backLink.title = 'Back to text';
        target.appendChild(backLink);
      }
      backLink.href = '#' + backId;
      backLink.onclick = function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const backTarget = document.getElementById(backId);
        if (backTarget) {
          scrollToWithOffset(backTarget, headerOffset);
          backTarget.classList.add('cite-back-highlight');
          setTimeout(() => backTarget.classList.remove('cite-back-highlight'), 2000);
        }
      };
    });
  });

  // --- Figure gallery horizontal controls ---
  document.querySelectorAll('[data-figure-gallery]').forEach(gallery => {
    const track = gallery.querySelector('.figure-gallery-track');
    const prev = gallery.querySelector('[data-gallery-prev]');
    const next = gallery.querySelector('[data-gallery-next]');
    if (!track || !prev || !next) return;

    const scrollByPage = direction => {
      const amount = Math.max(280, Math.floor(track.clientWidth * 0.82));
      track.scrollBy({ left: amount * direction, behavior: 'smooth' });
    };

    prev.addEventListener('click', () => scrollByPage(-1));
    next.addEventListener('click', () => scrollByPage(1));
  });

  // --- In-page image lightbox ---
  const triggers = Array.from(document.querySelectorAll('[data-lightbox-src]'));
  if (!triggers.length) return;

  const overlay = document.createElement('div');
  overlay.className = 'image-lightbox';
  overlay.hidden = true;
  overlay.innerHTML = [
    '<button type="button" class="image-lightbox-close" aria-label="Close image">X</button>',
    '<button type="button" class="image-lightbox-nav image-lightbox-prev" aria-label="Previous image">&lt;</button>',
    '<div class="image-lightbox-stage">',
    '  <img class="image-lightbox-img" alt="">',
    '</div>',
    '<button type="button" class="image-lightbox-nav image-lightbox-next" aria-label="Next image">&gt;</button>',
    '<div class="image-lightbox-footer">',
    '  <div class="image-lightbox-caption"></div>',
    '  <div class="image-lightbox-counter"></div>',
    '</div>'
  ].join('');
  document.body.appendChild(overlay);

  const lightboxImg = overlay.querySelector('.image-lightbox-img');
  const lightboxCaption = overlay.querySelector('.image-lightbox-caption');
  const lightboxCounter = overlay.querySelector('.image-lightbox-counter');
  const closeBtn = overlay.querySelector('.image-lightbox-close');
  const prevBtn = overlay.querySelector('.image-lightbox-prev');
  const nextBtn = overlay.querySelector('.image-lightbox-next');

  let activeItems = [];
  let activeIndex = 0;

  function itemsForTrigger(trigger) {
    const gallery = trigger.closest('[data-figure-gallery]');
    const scope = gallery || document;
    return Array.from(scope.querySelectorAll('[data-lightbox-src]')).map(el => ({
      src: el.dataset.lightboxSrc,
      caption: el.dataset.lightboxCaption || el.querySelector('img')?.alt || '',
      alt: el.querySelector('img')?.alt || el.dataset.lightboxCaption || ''
    }));
  }

  function renderLightbox() {
    const item = activeItems[activeIndex];
    if (!item) return;
    lightboxImg.src = item.src;
    lightboxImg.alt = item.alt;
    lightboxCaption.textContent = item.caption;
    lightboxCounter.textContent = activeItems.length > 1 ? `${activeIndex + 1} / ${activeItems.length}` : '';
    prevBtn.hidden = activeItems.length < 2;
    nextBtn.hidden = activeItems.length < 2;
  }

  function openLightbox(trigger) {
    activeItems = itemsForTrigger(trigger);
    activeIndex = Math.max(0, activeItems.findIndex(item => item.src === trigger.dataset.lightboxSrc));
    renderLightbox();
    overlay.hidden = false;
    document.body.classList.add('lightbox-open');
    closeBtn.focus({ preventScroll: true });
  }

  function closeLightbox() {
    overlay.hidden = true;
    document.body.classList.remove('lightbox-open');
    lightboxImg.removeAttribute('src');
  }

  function stepLightbox(delta) {
    if (activeItems.length < 2) return;
    activeIndex = (activeIndex + delta + activeItems.length) % activeItems.length;
    renderLightbox();
  }

  triggers.forEach(trigger => {
    trigger.addEventListener('click', event => {
      event.preventDefault();
      openLightbox(trigger);
    });
  });

  closeBtn.addEventListener('click', closeLightbox);
  prevBtn.addEventListener('click', () => stepLightbox(-1));
  nextBtn.addEventListener('click', () => stepLightbox(1));
  overlay.addEventListener('click', event => {
    if (event.target === overlay || event.target.classList.contains('image-lightbox-stage')) {
      closeLightbox();
    }
  });
  document.addEventListener('keydown', event => {
    if (overlay.hidden) return;
    if (event.key === 'Escape') closeLightbox();
    if (event.key === 'ArrowLeft') stepLightbox(-1);
    if (event.key === 'ArrowRight') stepLightbox(1);
  });
});
