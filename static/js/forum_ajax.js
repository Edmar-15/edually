/**
 * forum-ajax.js
 * --------------------------------------------------------------
 * Handles all generic AJAX interactions:
 *   • Forms with class .ajax-form
 *   • Delete buttons (class .ajax-delete-btn)
 *   • Pagination links inside #post-list
 *   • Loading modal content (class .ajax-modal)
 * --------------------------------------------------------------
 */
document.addEventListener('DOMContentLoaded', () => {
    /** -----------------------------------------------------------------
     *  Get CSRF token from cookie (same logic as in forum-upvote.js)
     *  ----------------------------------------------------------------- */
    const getCsrfToken = () => {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    /** -----------------------------------------------------------------
     *  1.  Generic form submit (POST) – expects JSON {success, html, …}
     *  ----------------------------------------------------------------- */
    document.body.addEventListener('submit', async e => {
        const form = e.target;
        if (!form.classList.contains('ajax-form')) return;
        e.preventDefault();

        const url = form.action;
        const method = (form.method || 'POST').toUpperCase();
        const formData = new FormData(form);
        const csrf = getCsrfToken();

        try {
            const resp = await fetch(url, {
                method,
                body: formData,
                headers: {
                    'X-CSRFToken': csrf,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            const data = await resp.json();

            if (!data.success) {
                // Replace the modal/body with the HTML that contains the error message
                if (form.dataset.target) {
                    const container = document.querySelector(form.dataset.target);
                    if (container) container.innerHTML = data.html || '';
                }
                return;
            }

            // -----------------------------------------------------------------
            // Insert / replace HTML according to data-* attributes
            // -----------------------------------------------------------------
            const targetSel = form.dataset.target;
            if (targetSel) {
                const container = document.querySelector(targetSel);
                if (!container) return;

                const insertMode = form.dataset.insert || (form.dataset.replace ? 'replace' : 'append');

                if (insertMode === 'prepend') {
                    container.insertAdjacentHTML('afterbegin', data.html);
                } else if (insertMode === 'append') {
                    container.insertAdjacentHTML('beforeend', data.html);
                } else if (insertMode === 'replace') {
                    container.outerHTML = data.html;
                } else {
                    container.innerHTML = data.html;
                }
            }

            // If a heading (like the reply count) should be updated
            if (form.dataset.after && data.replies_cnt !== undefined) {
                const heading = document.querySelector(form.dataset.after);
                if (heading) {
                    heading.textContent = `${data.replies_cnt} Reply${data.replies_cnt === 1 ? '' : 's'}`;
                }
            }

            // Close modal if the form lives inside one
            const modal = form.closest('.modal');
            if (modal) modal.classList.remove('open');
        } catch (err) {
            console.error('AJAX form error:', err);
        }
    });

    /** -----------------------------------------------------------------
     *  2.  Delete button (class .ajax-delete-btn)
     *  ----------------------------------------------------------------- */
    document.body.addEventListener('click', async e => {
        const btn = e.target.closest('.ajax-delete-btn');
        if (!btn) return;
        e.preventDefault();

        if (!confirm('Are you sure you want to delete this?')) return;

        const url = btn.dataset.url;
        const targetSel = btn.dataset.target;
        const csrf = getCsrfToken();

        try {
            const resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrf,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            const data = await resp.json();
            if (data.success && targetSel) {
                const el = document.querySelector(targetSel);
                if (el) el.remove();
            }
        } catch (err) {
            console.error('AJAX delete error:', err);
        }
    });

    /** -----------------------------------------------------------------
     *  3.  Pagination links inside #post-list
     *  ----------------------------------------------------------------- */
    document.body.addEventListener('click', async e => {
        const link = e.target.closest('.pagination a');
        if (!link) return;
        e.preventDefault();

        const url = link.href;
        try {
            const resp = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await resp.json();
            if (data.html) {
                const container = document.querySelector('#post-list');
                if (container) container.innerHTML = data.html;
            }
        } catch (err) {
            console.error('AJAX pagination error:', err);
        }
    });

    /** -----------------------------------------------------------------
     *  4.  Load modal content (class .ajax-modal)
     *  ----------------------------------------------------------------- */
    document.body.addEventListener('click', async e => {
        const btn = e.target.closest('.ajax-modal');
        if (!btn) return;
        e.preventDefault();

        const url = btn.dataset.ajaxUrl;
        const targetSel = btn.dataset.target || '#global-modal';
        const modal = document.querySelector(targetSel);

        if (!modal) return;

        try {
            const resp = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await resp.json();
            if (data.html) {
                modal.innerHTML = data.html;
                modal.classList.add('open');
            }
        } catch (err) {
            console.error('AJAX modal load error:', err);
        }
    });

    /** -----------------------------------------------------------------
     *  Optional: click outside modal to close it
     *  ----------------------------------------------------------------- */
    document.body.addEventListener('click', e => {
        if (e.target.classList.contains('modal')) {
            e.target.classList.remove('open');
        }
    });
});
