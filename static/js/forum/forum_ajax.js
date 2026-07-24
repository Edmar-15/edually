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

            if (data.deleted_id) {
                const deletedPost = document.querySelector(`#post-${data.deleted_id}`);
                const deletedReply = document.querySelector(`#reply-${data.deleted_id}`);
                const deletedEl = deletedPost || deletedReply;
                if (deletedEl) deletedEl.remove();
            }

            // If a heading (like the reply count) should be updated
            if (data.replies_cnt !== undefined) {
                const headingSelector = form.dataset.after;
                if (headingSelector) {
                    const heading = document.querySelector(headingSelector);
                    if (heading) {
                        heading.textContent = `${data.replies_cnt} Reply${data.replies_cnt === 1 ? '' : 's'}`;
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
     *  4.  Load modal content (class .ajax-modal) + accessibility
     *      - focus trap
     *      - restore focus on close
     *      - close on Escape
     *  ----------------------------------------------------------------- */
    let activeModal = null;
    let lastFocused = null;
    let modalObserver = null;
    let originalBodyOverflow = '';
    let originalBodyPaddingRight = '';

    const focusableSelector = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

    function lockBodyScroll() {
        originalBodyOverflow = document.body.style.overflow || '';
        originalBodyPaddingRight = document.body.style.paddingRight || '';

        document.body.style.overflow = 'hidden';
    }

    function unlockBodyScroll() {
        document.body.style.overflow = originalBodyOverflow;
        document.body.style.paddingRight = originalBodyPaddingRight;
    }

    function getFocusable(container) {
        if (!container) return [];
        return Array.from(container.querySelectorAll(focusableSelector)).filter(el => el.offsetParent !== null);
    }

    function openModal(modal) {
        if (!modal) return;
        lastFocused = document.activeElement;
        activeModal = modal;
        // prevent background scroll
        lockBodyScroll();
        document.body.classList.add('modal-open');
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-hidden', 'false');

        // focus first focusable element, or the modal itself
        const focusables = getFocusable(modal);
        if (focusables.length) focusables[0].focus();
        else modal.focus();

        // keydown handler for Tab / Escape
        modal._keydownHandler = function (ev) {
            if (ev.key === 'Escape') {
                ev.preventDefault();
                closeModal(modal);
                return;
            }
            if (ev.key === 'Tab') {
                const nodes = getFocusable(modal);
                if (!nodes.length) {
                    ev.preventDefault();
                    return;
                }
                const first = nodes[0];
                const last = nodes[nodes.length - 1];
                if (ev.shiftKey && document.activeElement === first) {
                    ev.preventDefault();
                    last.focus();
                } else if (!ev.shiftKey && document.activeElement === last) {
                    ev.preventDefault();
                    first.focus();
                }
            }
        };
        modal.addEventListener('keydown', modal._keydownHandler);

        // MutationObserver to detect when modal is closed by other codepaths
        modalObserver = new MutationObserver(mutations => {
            mutations.forEach(m => {
                if (m.attributeName === 'class') {
                    const oldVal = m.oldValue || '';
                    const wasOpen = oldVal.includes('open');
                    const isOpen = modal.classList.contains('open');
                    if (wasOpen && !isOpen) {
                        closeModal(modal);
                    }
                }
            });
        });
        modalObserver.observe(modal, { attributes: true, attributeOldValue: true, attributeFilter: ['class'] });
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        modal.removeAttribute('aria-modal');
        modal.removeAttribute('role');

        if (modal._keydownHandler) {
            modal.removeEventListener('keydown', modal._keydownHandler);
            delete modal._keydownHandler;
        }

        if (modalObserver) {
            modalObserver.disconnect();
            modalObserver = null;
        }

        // Restore focus
        try {
            if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
        } catch (err) { /* ignore */ }

        // restore body scrolling
        document.body.classList.remove('modal-open');
        unlockBodyScroll();

        activeModal = null;
        lastFocused = null;
    }

    document.body.addEventListener('click', async e => {
        const btn = e.target.closest('.ajax-modal');
        if (!btn) return;
        e.preventDefault();

        const confirmMessage = btn.dataset.confirm;
        if (confirmMessage && !confirmAction(confirmMessage)) return;

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
                // ensure modal is focusable
                modal.tabIndex = -1;
                openModal(modal);
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
});
