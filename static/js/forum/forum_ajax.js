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

    const confirmAction = (message) => {
        if (!message) return true;
        return confirm(message);
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
            if (targetSel && data.html !== undefined) {
                const container = document.querySelector(targetSel);
                if (!container) return;

                const insertMode = form.dataset.insert || (form.dataset.replace ? 'replace' : 'append');

                if (insertMode === 'prepend') {
                    container.insertAdjacentHTML('afterbegin', data.html);
                } else if (insertMode === 'append') {
                    container.querySelector('.reply-empty-state')?.remove();
                    container.insertAdjacentHTML('beforeend', data.html);
                } else if (insertMode === 'replace') {
                    if (container.classList.contains('modal')) {
                        container.innerHTML = data.html;
                    } else {
                        container.outerHTML = data.html;
                    }
                } else {
                    container.innerHTML = data.html;
                }
            }

            if (form.classList.contains('reply-form')) {
                form.reset();
            }

            const removalId = data.deleted_id || data.archived_id;
            if (removalId) {
                const deletedPost = document.querySelector(`#post-${removalId}`);
                const deletedReply = document.querySelector(`#reply-${removalId}`);
                const removedEl = deletedPost || deletedReply;
                if (removedEl) removedEl.remove();
            }

            // -----------------------------------------------------------------
            // 6.  If a heading (like the reply count) should be updated
            // -----------------------------------------------------------------
             if (data.replies_cnt !== undefined) {
                 const headingSelector = form.dataset.after;
                 if (headingSelector) {
                     const heading = document.querySelector(headingSelector);
                     if (heading) {
                        heading.textContent = `${data.replies_cnt} ${data.replies_cnt === 1 ? 'Response' : 'Responses'}`;
                    }
                }

                const postId = form.dataset.postId || form.closest('.post-item')?.dataset.postId;
                const badgeTargets = postId
                    ? Array.from(document.querySelectorAll(`.post-item[data-post-id="${postId}"] .reply-count-badge`))
                    : Array.from(document.querySelectorAll('.reply-count-badge'));

                badgeTargets.forEach(badge => {
                    if (badge) badge.textContent = data.replies_cnt;
                });
            }

            // Redirect if requested by the server
            if (data.redirect) {
                window.location.href = data.redirect;
                return;
            }

            // Close modal if the form lives inside one
            const modal = form.closest('.modal');
            const closeModal = form.dataset.closeModal !== 'false';
            if (closeModal && modal) modal.classList.remove('open');
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

        const confirmMessage = btn.dataset.confirm || 'Are you sure you want to delete this?';
        if (!confirmAction(confirmMessage)) return;

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
     *  Optional: click outside modal to close it
     *  ----------------------------------------------------------------- */
    document.body.addEventListener('click', e => {
        if (e.target.classList.contains('modal')) {
            e.target.classList.remove('open');
            return;
        }

        const toggle = e.target.closest('.action-menu-toggle');
        if (toggle) {
            const menu = toggle.closest('.action-menu');
            if (!menu) return;
            const panel = menu.querySelector('.action-menu-panel');
            if (!panel) return;
            const expanded = toggle.getAttribute('aria-expanded') === 'true';
            if (!expanded) {
                panel.classList.add('up');
            } else {
                panel.classList.remove('up');
            }
            menu.classList.toggle('open', !expanded);
            panel.classList.toggle('open', !expanded);
            toggle.setAttribute('aria-expanded', String(!expanded));
            panel.setAttribute('aria-hidden', String(expanded));
            return;
        }

        document.querySelectorAll('.action-menu.open').forEach(menu => {
            const panel = menu.querySelector('.action-menu-panel');
            const toggle = menu.querySelector('.action-menu-toggle');
            menu.classList.remove('open');
            if (panel) panel.classList.remove('open');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
            if (panel) panel.setAttribute('aria-hidden', 'true');
        });
    });

    /** -----------------------------------------------------------------
     *  Sort trigger button toggle
     *  ----------------------------------------------------------------- */
    document.body.addEventListener('click', e => {
        const sortTrigger = e.target.closest('.sort-trigger');
        if (sortTrigger) {
            const sortGroup = sortTrigger.closest('.sort-group');
            if (!sortGroup) return;
            const sortOptions = sortGroup.querySelector('.sort-options');
            if (!sortOptions) return;
            e.preventDefault();
            e.stopPropagation();
            sortOptions.classList.toggle('open');
            sortTrigger.setAttribute('aria-expanded', String(sortOptions.classList.contains('open')));
            return;
        }

        // Close sort options when clicking a sort option
        const sortOption = e.target.closest('.sort-option');
        if (sortOption) {
            const sortOptions = sortOption.closest('.sort-options');
            if (sortOptions) {
                sortOptions.classList.remove('open');
                const trigger = sortOptions.closest('.sort-group')?.querySelector('.sort-trigger');
                if (trigger) trigger.setAttribute('aria-expanded', 'false');
            }
            return;
        }

        // Close sort options when clicking outside
        const inSortGroup = e.target.closest('.sort-group');
        if (!inSortGroup) {
            document.querySelectorAll('.sort-options.open').forEach(options => {
                options.classList.remove('open');
                const trigger = options.closest('.sort-group')?.querySelector('.sort-trigger');
                if (trigger) trigger.setAttribute('aria-expanded', 'false');
            });
        }
    });

    document.addEventListener('click', async function (e) {
        // The button lives inside the global modal that is loaded via
        // the js‑modal‑trigger on the bell icon.
        const btn = e.target.closest('#mark-all-read-btn');
        if (!btn) return;
        e.preventDefault();

        const url = btn.dataset.url;
        try {
            const resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'X‑CSRFToken': getCsrfToken(),
                    'X‑Requested‑With': 'XMLHttpRequest',
                },
            });
            const data = await resp.json();

            if (data.success) {
                // 1️⃣ Remove the red badge that shows the unread count
                const badge = document.getElementById('notification-badge');
                if (badge) badge.remove();

                // 2️⃣ Inside the modal, turn every <li class="unread"> → normal
                const modal = document.getElementById('global-modal');
                if (modal) {
                    modal.querySelectorAll('li.unread')
                        .forEach(li => li.classList.remove('unread'));
                }
            }
        } catch (err) {
            console.error('Mark‑all‑read failed', err);
        }
    });
});