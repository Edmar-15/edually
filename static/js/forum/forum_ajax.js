document.addEventListener('DOMContentLoaded', () => {
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

    const showToast = (message, type = 'info') => {
        if (typeof window.showGlobalToast === 'function') {
            window.showGlobalToast(message, type);
        } else {
            console.error('SweetAlert2 notification is unavailable:', message);
        }
    };

    const confirmAction = async (message) => {
        if (!message) return true;
        if (!window.Swal) {
            showToast('Confirmation is unavailable. Refresh the page and try again.', 'error');
            return false; // Never perform a destructive action without confirmation.
        }
        const result = await window.Swal.fire({
            title: 'Confirm action',
            text: message,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Confirm',
            cancelButtonText: 'Cancel',
            focusCancel: true,
            reverseButtons: true,
        });
        return result.isConfirmed;
    };

    const rememberRedirectToast = (message, type = 'success') => {
        if (!message) return;
        try {
            sessionStorage.setItem('eduallyToastMessage', JSON.stringify({ message, type }));
        } catch (error) {
            console.warn('Could not queue redirect notification:', error);
        }
    };

    document.body.addEventListener('submit', async e => {
        const form = e.target;
        if (!form.classList.contains('ajax-form') || form.hasAttribute('data-modal-form')) return;
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
            if (!resp.ok) throw new Error(`Request failed (${resp.status})`);
            const data = await resp.json();

            if (!data.success) {
                // Preserve the existing reply list: the server may send only an
                // error fragment, which should never replace all replies.
                if (data.html && form.dataset.target) {
                    const container = document.querySelector(form.dataset.target);
                    if (container?.classList.contains('modal')) container.innerHTML = data.html;
                }
                showToast(data.error || data.message || 'Could not submit. Please check your input.', 'error');
                return;
            }

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

            if (data.redirect) {
                rememberRedirectToast(data.message, data.toastType || 'success');
                window.location.href = data.redirect;
                return;
            }

            if (data.message || form.classList.contains('reply-form')) {
                showToast(data.message || 'Reply posted successfully.', data.toastType || 'success');
            }

            const modal = form.closest('.modal');
            const closeModal = form.dataset.closeModal !== 'false';
            if (closeModal && modal) modal.classList.remove('open');
        } catch (err) {
            console.error('AJAX form error:', err);
            showToast('Could not submit your changes. Please try again.', 'error');
        }
    });

    document.body.addEventListener('click', async e => {
        const btn = e.target.closest('.ajax-delete-btn');
        if (!btn) return;
        e.preventDefault();

        const confirmMessage = btn.dataset.confirm || 'Are you sure you want to delete this?';
        if (!await confirmAction(confirmMessage)) return;

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
            if (!resp.ok) throw new Error(`Delete failed (${resp.status})`);
            const data = await resp.json();
            if (data.success) {
                if (targetSel) {
                    const el = document.querySelector(targetSel);
                    if (el) el.remove();
                }
                showToast(data.message || 'Deleted successfully.', 'success');
            } else {
                showToast(data.error || data.message || 'Could not delete this item.', 'error');
            }
        } catch (err) {
            console.error('AJAX delete error:', err);
            showToast('Could not delete this item. Please try again.', 'error');
        }
    });

    document.body.addEventListener('click', async e => {
        const link = e.target.closest('.pagination a');
        if (!link) return;
        e.preventDefault();

        const url = link.href;
        try {
            const resp = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!resp.ok) throw new Error(`Pagination failed (${resp.status})`);
            const data = await resp.json();
            if (data.html) {
                const container = document.querySelector('#post-list');
                if (container) container.innerHTML = data.html;
            } else {
                showToast('Could not load more discussions.', 'error');
            }
        } catch (err) {
            console.error('AJAX pagination error:', err);
            showToast('Could not load more discussions. Please try again.', 'error');
        }
    });

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
            const menuContainer = menu.closest('.post-card, .post-item, .reply-item, .question-card, .post-detail');

            if (!expanded) {
                document.querySelectorAll('.action-menu.open').forEach(openMenu => {
                    if (openMenu === menu) return;
                    openMenu.classList.remove('open');
                    openMenu.querySelector('.action-menu-panel')?.classList.remove('open', 'up');
                    openMenu.querySelector('.action-menu-toggle')?.setAttribute('aria-expanded', 'false');
                    openMenu.querySelector('.action-menu-panel')?.setAttribute('aria-hidden', 'true');
                    openMenu.closest('.post-card, .post-item, .reply-item, .question-card, .post-detail')
                        ?.classList.remove('has-open-action-menu');
                });
            }

            if (!expanded) {
                const toggleRect = toggle.getBoundingClientRect();
                const header = document.querySelector('.content-header');
                const headerBottom = header ? Math.max(0, header.getBoundingClientRect().bottom) : 0;
                const availableAbove = Math.max(0, toggleRect.top - headerBottom - 12);
                const availableBelow = Math.max(0, window.innerHeight - toggleRect.bottom - 12);
                panel.style.maxHeight = ''; // Measure the natural menu height.
                const panelHeight = panel.offsetHeight;
                const openUp = availableBelow < panelHeight + 8 && availableAbove > availableBelow;
                panel.classList.toggle('up', openUp);
                panel.style.maxHeight = `${Math.floor(openUp ? availableAbove : availableBelow)}px`;
            } else {
                panel.classList.remove('up');
            }
            menu.classList.toggle('open', !expanded);
            panel.classList.toggle('open', !expanded);
            menuContainer?.classList.toggle('has-open-action-menu', !expanded);
            toggle.setAttribute('aria-expanded', String(!expanded));
            panel.setAttribute('aria-hidden', String(expanded));
            return;
        }

        document.querySelectorAll('.action-menu.open').forEach(menu => {
            const panel = menu.querySelector('.action-menu-panel');
            const toggle = menu.querySelector('.action-menu-toggle');
            menu.classList.remove('open');
            if (panel) panel.classList.remove('open', 'up');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
            if (panel) panel.setAttribute('aria-hidden', 'true');
            menu.closest('.post-card, .post-item, .reply-item, .question-card, .post-detail')
                ?.classList.remove('has-open-action-menu');
        });
    });

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

        const inSortGroup = e.target.closest('.sort-group');
        if (!inSortGroup) {
            document.querySelectorAll('.sort-options.open').forEach(options => {
                options.classList.remove('open');
                const trigger = options.closest('.sort-group')?.querySelector('.sort-trigger');
                if (trigger) trigger.setAttribute('aria-expanded', 'false');
            });
        }
    });

});
