const notificationQueue = [];
let isDisplayingNotification = false;

window.showGlobalToast = (message, type = 'info', duration = 4000) => {
  if (!message) return;

  if (!window.Swal) {
    console.error('SweetAlert2 is unavailable; notification was not displayed.');
    return;
  }

  const icon = ['success', 'error', 'warning', 'info'].includes(type)
    ? type
    : 'info';
  const timer = Number.isFinite(duration) && duration > 0 ? duration : 4000;

  notificationQueue.push({ message: String(message), icon, timer });
  displayNextNotification();
};

function displayNextNotification() {
  if (isDisplayingNotification || notificationQueue.length === 0) return;

  if (!window.Swal) {
    notificationQueue.length = 0;
    console.error('SweetAlert2 is unavailable; queued notifications were discarded.');
    return;
  }

  const notification = notificationQueue.shift();
  isDisplayingNotification = true;

  window.Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    showCloseButton: true,
    timerProgressBar: true,
    customClass: {
      popup: 'edually-swal-toast',
    },
    didOpen: popup => {
      popup.addEventListener('mouseenter', window.Swal.stopTimer);
      popup.addEventListener('mouseleave', window.Swal.resumeTimer);
    },
  }).fire({
    title: notification.message,
    icon: notification.icon,
    timer: notification.timer,
  }).then(() => {
    isDisplayingNotification = false;
    displayNextNotification();
  }).catch(error => {
    isDisplayingNotification = false;
    console.error('Failed to display SweetAlert2 notification.', error);
    displayNextNotification();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const getMessagesLists = () =>
    Array.from(document.querySelectorAll('ul.messages'));

  const mapTagToType = className => {
    const lower = (className || '').toLowerCase();
    if (lower.includes('error') || lower.includes('danger')) return 'error';
    if (lower.includes('warning')) return 'warning';
    if (lower.includes('success')) return 'success';
    return 'info';
  };

  const renderMessages = () => {
    const renderedMessages = new Set();

    getMessagesLists().forEach(messagesList => {
      if (messagesList.dataset.toastHandled === 'true') return;
      messagesList.dataset.toastHandled = 'true';

      Array.from(messagesList.children).forEach(item => {
        if (!(item instanceof HTMLElement)) return;

        const type = mapTagToType(item.className);
        const text = item.textContent.trim();
        const messageKey = `${type}:${text}`;

        if (text && !renderedMessages.has(messageKey)) {
          renderedMessages.add(messageKey);
          window.showGlobalToast(text, type);
        }
      });

      messagesList.remove();
    });
  };

  const renderRedirectNotification = () => {
    let payload;
    try {
      payload = sessionStorage.getItem('eduallyToastMessage');
      if (!payload) return;

      const { message, type = 'info', duration = 4000 } = JSON.parse(payload);
      if (message) window.showGlobalToast(message, type, duration);
    } catch (error) {
      console.error('Failed to render redirect notification.', error);
    } finally {
      if (payload) sessionStorage.removeItem('eduallyToastMessage');
    }
  };

  renderMessages();
  renderRedirectNotification();
});
