/* --------------------------------------------------------------
   toast_notifications.js
   – Global toast system (right‑corner, glass‑morphism, close button)
   -------------------------------------------------------------- */

/* --------------------------------------------------------------
   1️⃣  Helper: get (or create) the outer container that holds
       all toast elements.
   -------------------------------------------------------------- */
const getToastContainer = () => {
  let container = document.querySelector('.toast-container');

  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    container.setAttribute('aria-live', 'polite');
    // The CSS we added positions this element on the right edge.
    document.body.appendChild(container);
  }

  return container;
};

/* --------------------------------------------------------------
   2️⃣  Core API – show a toast
   -------------------------------------------------------------- */
window.showGlobalToast = (
  /** The text you want to display */
  message,
  /** 'info' | 'success' | 'error' | 'warning'  */
  type = 'info',
  /** Milliseconds the toast stays visible (default 4 s) */
  duration = 4000
) => {
  if (!message) return;

  const container = getToastContainer();

  // ------------------------------------------------------------
  // Build the toast element
  // ------------------------------------------------------------
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');

  // Custom property used by CSS to time the slide‑out animation
  toast.style.setProperty('--toast-life', `${duration}ms`);

  // ----- Icon -------------------------------------------------
  const icon = document.createElement('span');
  icon.className = 'toast__icon';
  // Simple mapping – feel free to replace with SVGs later
  const iconMap = {
    success: '✓',
    error:   '✕',
    warning: '⚠',
    info:    'ℹ',
  };
  icon.textContent = iconMap[type] || 'ℹ';
  toast.appendChild(icon);

  // ----- Message -----------------------------------------------
  const msg = document.createElement('span');
  msg.textContent = message;
  toast.appendChild(msg);

  // ----- Close button (×) --------------------------------------
  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'toast__close';
  closeBtn.setAttribute('aria-label', 'Dismiss');
  closeBtn.innerHTML = '&times;';

  // Prevent the click from bubbling to the toast‑click handler
  closeBtn.addEventListener('click', e => {
    e.stopPropagation();
    toast.remove();
  });

  toast.appendChild(closeBtn);

  // ----- Click anywhere on toast removes it (quick dismiss) ---
  toast.addEventListener('click', () => toast.remove());

  // ----- Hover‑pause (so users can read it) --------------------
  toast.addEventListener('mouseenter', () => {
    toast.style.animationPlayState = 'paused';
  });
  toast.addEventListener('mouseleave', () => {
    toast.style.animationPlayState = 'running';
  });

  // ------------------------------------------------------------
  // Insert into DOM and schedule removal after the out‑animation
  // ------------------------------------------------------------
  container.appendChild(toast);

  // Buffer a little extra time (600 ms) for the slide‑out animation
  setTimeout(() => toast.remove(), duration + 600);
};

/* --------------------------------------------------------------
   3️⃣  Legacy support – turn `<ul class="messages">` into toasts
   -------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
  // -----------------------------------------------------------------
  // Helper: find every <ul class="messages"> on the page.
  // -----------------------------------------------------------------
  const getMessagesLists = () =>
    Array.from(document.querySelectorAll('ul.messages'));

  // -----------------------------------------------------------------
  // Map a list‑item's class name to a toast type.
  // -----------------------------------------------------------------
  const mapTagToType = className => {
    const lower = (className || '').toLowerCase();
    if (lower.includes('error') || lower.includes('danger')) return 'error';
    if (lower.includes('warning')) return 'warning';
    if (lower.includes('success')) return 'success';
    return 'info';
  };

  // -----------------------------------------------------------------
  // Render all toasts that were generated server‑side.
  // -----------------------------------------------------------------
  const renderToastsFromLists = () => {
    const container = getToastContainer();

    getMessagesLists().forEach(messagesList => {
      // Prevent double‑processing if the script re‑runs.
      if (messagesList.dataset.toastHandled === 'true') return;
      messagesList.dataset.toastHandled = 'true';

      Array.from(messagesList.children).forEach(item => {
        if (!(item instanceof HTMLElement)) return;

        const type = mapTagToType(item.className);
        const text = item.textContent.trim();

        if (text) {
          window.showGlobalToast(text, type);
        }
      });

      // Remove the original list – we don’t need it any more.
      messagesList.remove();
    });
  };

  // -----------------------------------------------------------------
  // Render any toast that was stored in sessionStorage (e.g., after a
  // redirect). The payload must be JSON: {message, type, duration}
  // -----------------------------------------------------------------
  const renderRedirectToast = () => {
    try {
      const payload = sessionStorage.getItem('eduallyToastMessage');
      if (!payload) return;

      const { message, type = 'info', duration = 4000 } = JSON.parse(payload);
      if (message) {
        window.showGlobalToast(message, type, duration);
      }
    } catch (e) {
      console.error('Failed to render redirect toast', e);
    } finally {
      // Clean up – we only want to show it once.
      sessionStorage.removeItem('eduallyToastMessage');
    }
  };

  // -----------------------------------------------------------------
  // Kick everything off.
  // -----------------------------------------------------------------
  renderToastsFromLists();
  renderRedirectToast();
});

/* --------------------------------------------------------------
   END OF toast_notifications.js
   -------------------------------------------------------------- */
