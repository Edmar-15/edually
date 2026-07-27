document.addEventListener('DOMContentLoaded', () => {
  const getMessagesLists = () => Array.from(document.querySelectorAll('ul.messages'));

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
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');
        toast.style.setProperty('--toast-life', '4000ms');

        const icon = document.createElement('span');
        icon.className = 'toast__icon';
        icon.textContent = type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '⚠' : 'ℹ';

        const message = document.createElement('span');
        message.textContent = item.textContent.trim();

        toast.appendChild(icon);
        toast.appendChild(message);
        toast.addEventListener('click', () => toast.remove());
        container.appendChild(toast);
      });

      messagesList.remove();
    });
  };

  renderToasts();
});
