const getToastContainer = () => {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    container.setAttribute('aria-live', 'polite');
    document.body.appendChild(container);
  }
  return container;
};

window.showGlobalToast = (message, type = 'info', duration = 4000) => {
  if (!message) return;

  const container = getToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.style.setProperty('--toast-life', `${duration}ms`);

  const icon = document.createElement('span');
  icon.className = 'toast__icon';
  icon.textContent = type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '⚠' : 'ℹ';

  const msg = document.createElement('span');
  msg.textContent = message;

  toast.appendChild(icon);
  toast.appendChild(msg);
  toast.addEventListener('click', () => toast.remove());
  container.appendChild(toast);
  setTimeout(() => toast.remove(), duration + 500);
};

document.addEventListener('DOMContentLoaded', () => {
  const getMessagesLists = () => Array.from(document.querySelectorAll('ul.messages'));

  const mapTagToType = (className = '') => {
    const normalized = className.toLowerCase();
    if (normalized.includes('error') || normalized.includes('danger')) return 'error';
    if (normalized.includes('warning')) return 'warning';
    if (normalized.includes('success')) return 'success';
    return 'info';
  };

  const renderToasts = () => {
    const container = getToastContainer();

    getMessagesLists().forEach((messagesList) => {
      if (messagesList.dataset.toastHandled === 'true') return;
      messagesList.dataset.toastHandled = 'true';

      Array.from(messagesList.children).forEach((item) => {
        if (!(item instanceof HTMLElement)) return;

        const type = mapTagToType(item.className);
        const message = item.textContent.trim();
        if (message) {
          window.showGlobalToast(message, type);
        }
      });

      messagesList.remove();
    });
  };

  renderToasts();

  const renderRedirectToast = () => {
    try {
      const payload = sessionStorage.getItem('eduallyToastMessage');
      if (!payload) return;

      const { message, type, duration } = JSON.parse(payload);
      if (message) {
        window.showGlobalToast(message, type, duration);
      }
    } catch (error) {
      console.error('Failed to render redirect toast', error);
    } finally {
      sessionStorage.removeItem('eduallyToastMessage');
    }
  };

  renderRedirectToast();
});
