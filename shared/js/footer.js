/* ============================================
   Shared Footer Component
   Single source of truth for site footer
   ============================================ */
(function() {
  var footer = document.getElementById('site-footer');
  if (!footer) return;

  footer.className = 'site-footer';
  footer.innerHTML =
    '<p>' +
      '&copy; 2026 <a href="https://terry.artlab.ai" target="_blank" rel="noopener" class="footer-author">Terry Taewoong Um</a>. ' +
      'Licensed under <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener" class="footer-license">CC BY-NC-SA 4.0</a>.' +
    '</p>';
})();
