document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-modal]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            const target = btn.dataset.modal;
            const modal = document.getElementById(`${target}-modal`);
            if (modal) modal.classList.remove('hidden');
        });
    });

    document.querySelectorAll('.policy-modal__close, .policy-modal__backdrop')
        .forEach(el => {
            el.addEventListener('click', e => {
                const modal = el.closest('.policy-modal');
                if (modal) modal.classList.add('hidden');
            });
        });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            const open = document.querySelector('.policy-modal:not(.hidden)');
            if (open) open.classList.add('hidden');
        }
    });
});