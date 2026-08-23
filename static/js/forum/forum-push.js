document.addEventListener('DOMContentLoaded', () => {
    const button = document.querySelector('[data-forum-push]');
    const modal = document.getElementById('global-modal');
    if (!button) return;

    const closeModal = () => {
        modal.classList.remove('open');
        modal.setAttribute('hidden', '');
        modal.innerHTML = '';
    };

    const openModal = () => {
        if (!modal) return;

        modal.innerHTML = `
            <div class="modal__backdrop" data-close-push-modal></div>
            <div class="modal__content forum-push-modal" role="document">
                <div class="modal__header">
                    <div>
                        <p class="eyebrow">Forum updates</p>
                        <h2 class="modal__title" id="forum-push-modal-title">Stay updated</h2>
                    </div>
                    <button type="button" class="modal__close" data-close-push-modal aria-label="Close notification dialog">&times;</button>
                </div>
                <div class="modal__body">
                    <p>Get an alert when someone replies to one of your discussions.</p>
                    <p class="forum-push-modal__status" data-push-status aria-live="polite"></p>
                </div>
                <div class="modal__footer">
                    <button type="button" class="button secondary-button" data-close-push-modal>Not now</button>
                    <button type="button" class="button primary-button" data-enable-push-modal>
                        <i class="fa-solid fa-bell" aria-hidden="true"></i> Enable notifications
                    </button>
                </div>
            </div>`;
        modal.removeAttribute('hidden');
        modal.classList.add('open');

        modal.querySelectorAll('[data-close-push-modal]').forEach((closeButton) => {
            closeButton.addEventListener('click', closeModal);
        });

        const enableButton = modal.querySelector('[data-enable-push-modal]');
        const status = modal.querySelector('[data-push-status]');
        enableButton.addEventListener('click', async () => {
            if (typeof window.enablePushNotifications !== 'function') {
                status.textContent = 'Push notifications are unavailable right now.';
                return;
            }

            enableButton.disabled = true;
            enableButton.setAttribute('aria-busy', 'true');
            try {
                const enabled = await window.enablePushNotifications();
                if (enabled) {
                    button.classList.add('is-enabled');
                    button.setAttribute('aria-label', 'Push notifications enabled');
                    button.title = 'Push notifications enabled';
                    closeModal();
                } else {
                    status.textContent = 'Notifications were not enabled. Please try again.';
                }
            } catch (error) {
                console.error('Failed to enable forum push notifications.', error);
                const detail = error && error.message ? ` (${error.message})` : '';
                status.textContent = `Could not enable notifications${detail}. Check that you are using localhost or HTTPS and that your browser can reach its push service.`;
            } finally {
                enableButton.disabled = false;
                enableButton.removeAttribute('aria-busy');
            }
        });

        enableButton.focus();
    };

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal && modal.classList.contains('open')) closeModal();
    });

    button.addEventListener('click', openModal);
});
