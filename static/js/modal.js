/* static/js/modal.js -------------------------------------------------
   A tiny, dependency‑free modal loader.
   --------------------------------------------------------------- */

(() => {
    const modal = document.getElementById('global-modal');

    /* -----------------------------------------------------------------
       Helper – read a cookie (used for CSRF token)
       ----------------------------------------------------------------- */
    const getCookie = name => {
        const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return match ? decodeURIComponent(match.pop()) : '';
    };

    /* -----------------------------------------------------------------
       Close the modal and clean its content
       ----------------------------------------------------------------- */
    const closeModal = () => {
        modal.classList.remove('open');
        modal.setAttribute('hidden', '');
        modal.innerHTML = '';
    };

    /* -----------------------------------------------------------------
       Attach close behaviour (backdrop click, ESC, X‑button)
       ----------------------------------------------------------------- */
    const bindCloseEvents = () => {
        // Click on backdrop or any element with data-close-modal
        modal.addEventListener('click', e => {
            if (e.target.dataset.closeModal !== undefined ||
                e.target.classList.contains('modal__backdrop')) {
                closeModal();
            }
        });

        // Press ESC
        const escHandler = e => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    };

    /* -----------------------------------------------------------------
       Turn a <form> inside the modal into an AJAX POST
       ----------------------------------------------------------------- */
    const bindAjaxForm = form => {
        form.addEventListener('submit', async e => {
            e.preventDefault();

            const action = form.action;
            const method = form.method.toUpperCase();

            const formData = new FormData(form);
            const csrf = getCookie('csrftoken');

            const response = await fetch(action, {
                method,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrf,
                },
                credentials: 'same-origin',
                body: formData,
            });

            const data = await response.json();
            if (data.success && data.redirect) {
                // Full page navigation – logout, delete, etc.
                window.location.href = data.redirect;
            } else {
                // For safety, reload the page if something went wrong.
                window.location.reload();
            }
        });
    };

    /* -----------------------------------------------------------------
       Load modal content from a URL that returns JSON {html: …}
       ----------------------------------------------------------------- */
    const openModalFromUrl = async url => {
        try {
            const resp = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                },
                credentials: 'same-origin',
            });

            if (!resp.ok) throw new Error('Network error');

            const data = await resp.json();
            if (!data.html) throw new Error('No HTML payload');

            // Inject the HTML and open the modal
            modal.innerHTML = data.html.trim();
            modal.removeAttribute('hidden');
            modal.classList.add('open');

            // Give focus to the first focusable element inside the dialog
            const focusable = modal.querySelector('[autofocus]') ||
                              modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            focusable && focusable.focus();

            // Wire things up
            bindCloseEvents();

            // If there's a form (logout, delete, etc.) attach AJAX submit
            const modalForm = modal.querySelector('form[data-modal-form]');
            if (modalForm) bindAjaxForm(modalForm);
        } catch (err) {
            console.error('Modal load failed', err);
        }
    };

    /* -----------------------------------------------------------------
       Attach click listeners to any element with .js-modal-trigger
       ----------------------------------------------------------------- */
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.js-modal-trigger').forEach(el => {
            el.addEventListener('click', e => {
                e.preventDefault();
                const url = el.dataset.url || el.getAttribute('href');
                if (url) openModalFromUrl(url);
            });
        });
    });
})();
