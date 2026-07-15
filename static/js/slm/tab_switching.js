document.addEventListener('DOMContentLoaded', () => {
  // One handler per .tabs container (you can have many on a page)
  document.querySelectorAll('.tabs').forEach(container => {
    const tabs   = container.querySelectorAll('[role="tab"]');
    const panels = container.querySelectorAll('[role="tabpanel"]');

    // -----------------------------------------------------------------
    // Helper – set the UI for a given index (same as before)
    // -----------------------------------------------------------------
    const activate = (newIdx) => {
      tabs.forEach((t, i) => {
        const isActive = i === newIdx;
        t.setAttribute('aria-selected', isActive);
        t.setAttribute('tabindex', isActive ? '0' : '-1');
        t.classList.toggle('active', isActive);
        const desc = t.querySelector('.tab-desc');
        if (desc) desc.setAttribute('aria-hidden', !isActive);
      });

      panels.forEach((p, i) => {
        const show = i === newIdx;
        p.hidden = !show;
        p.setAttribute('aria-hidden', !show);
      });

      // Give keyboard focus to the newly‑selected tab
      tabs[newIdx].focus();
    };

    // -----------------------------------------------------------------
    // New: activate the tab that matches the current URL hash (if any)
    // -----------------------------------------------------------------
    const activateFromHash = () => {
      const hash = window.location.hash;               // e.g. "#tab-1"
      if (!hash) return;                               // no hash → keep default

      // Find the tab button whose id matches the hash (strip the leading “#”)
      const targetTab = container.querySelector(`button${hash}`);
      if (!targetTab) return;                         // unknown hash → ignore

      // Compute its index among all tabs and activate it
      const idx = Array.from(tabs).indexOf(targetTab);
      if (idx >= 0) activate(idx);
    };

    // -----------------------------------------------------------------
    // Click → activate (unchanged)
    // -----------------------------------------------------------------
    tabs.forEach((tab, idx) => tab.addEventListener('click', () => activate(idx)));

    // -----------------------------------------------------------------
    // Keyboard navigation (← → Home End) – unchanged
    // -----------------------------------------------------------------
    container.addEventListener('keydown', e => {
      const curIdx = Array.from(tabs).findIndex(t => t.getAttribute('aria-selected') === 'true');
      let nextIdx = null;
      switch (e.key) {
        case 'ArrowRight': nextIdx = (curIdx + 1) % tabs.length; break;
        case 'ArrowLeft':  nextIdx = (curIdx - 1 + tabs.length) % tabs.length; break;
        case 'Home':       nextIdx = 0; break;
        case 'End':        nextIdx = tabs.length - 1; break;
        default: return;
      }
      e.preventDefault();
      activate(nextIdx);
    });

    // -----------------------------------------------------------------
    // **Run the hash‑based activation **as the very first step
    // -----------------------------------------------------------------
    activateFromHash();           // <‑‑ this line makes the hash work
  });
});