document.addEventListener('DOMContentLoaded', () => {
    const dialog = document.getElementById('forum-sidebar-dialog');
    const title = document.getElementById('forum-sidebar-dialog-title');
    if (!dialog || !title) return;

    const panels = dialog.querySelectorAll('.forum-sidebar-dialog-panel');

    document.querySelectorAll('[data-forum-sidebar-panel]').forEach((button) => {
        button.addEventListener('click', () => {
            const selectedPanel = button.dataset.forumSidebarPanel;
            panels.forEach((panel) => {
                panel.hidden = panel.id !== selectedPanel;
            });
            title.textContent = button.dataset.forumSidebarTitle;
            dialog.showModal();
        });
    });

    dialog.addEventListener('click', (event) => {
        if (event.target === dialog || event.target.closest('.js-modal-trigger')) {
            dialog.close();
        }
    });
});