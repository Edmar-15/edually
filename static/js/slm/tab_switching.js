// ---------------------------------------------------------------
// tab_switching.js – remember the active tab via URL hash
// ---------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // One handler per .tabs container (you can have many on a page)
  document.querySelectorAll('.tabs').forEach(container => {
    const tabs   = container.querySelectorAll('[role="tab"]');
    const panels = container.querySelectorAll('[role="tabpanel"]');

    // -----------------------------------------------------------------
    // A stable key for local‑storage (in case a page has more than one
    // tab‑set).  You can also drop the localStorage part if you only
    // care about the hash.
    // -----------------------------------------------------------------
    const storageKey = `activeTab_${container.id || 'default'}`;

    // -----------------------------------------------------------------
    // Activate a tab – also writes the hash and stores the index.
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

      // ---- 1) write a hash so it survives a page‑reload -------------
      const newHash = `#${tabs[newIdx].id}`;
      if (window.location.hash !== newHash) {
        // replaceState prevents an extra history entry
        history.replaceState(null, '', newHash);
      }

      // ---- 2) store the index for the fallback when no hash is set --
      localStorage.setItem(storageKey, newIdx);

      // Give keyboard focus to the newly‑selected tab
      tabs[newIdx].focus();
    };

    // -----------------------------------------------------------------
    // Activate the tab that matches the current URL hash (if any)
    // -----------------------------------------------------------------
    const activateFromHash = () => {
      const hash = window.location.hash;               // e.g. "#tab-1"
      if (!hash) return false;

      const targetTab = container.querySelector(`button${hash}`);
      if (!targetTab) return false;

      const idx = Array.from(tabs).indexOf(targetTab);
      if (idx >= 0) {
        activate(idx);
        return true;
      }
      return false;
    };

    // -----------------------------------------------------------------
    // Click → activate (unchanged logic)
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
    // ----  Initial activation  ---------------------------------------
    // 1️⃣  Try hash first
    // 2️⃣  If there is *no* hash, fall back to the saved index
    // 3️⃣  If nothing was saved, keep the server‑rendered default (first tab)
    // -----------------------------------------------------------------
    if (!activateFromHash()) {
      const saved = localStorage.getItem(storageKey);
      const idx   = Number(saved);
      if (!isNaN(idx) && idx >= 0 && idx < tabs.length) {
        activate(idx);
      }
    }
  });
});
