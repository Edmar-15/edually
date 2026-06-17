document.addEventListener('DOMContentLoaded', () => {
    // 1️⃣ openers – any element with data‑modal="terms" or "privacy"
    document.querySelectorAll('[data-modal]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            const target = btn.dataset.modal;                // "terms" or "privacy"
            const modal = document.getElementById(`${target}-modal`);
            if (modal) modal.classList.remove('hidden');
        });
    });

    // 2️⃣ closers – X button or backdrop
    document.querySelectorAll('.policy-modal__close, .policy-modal__backdrop')
        .forEach(el => {
            el.addEventListener('click', e => {
                const modal = el.closest('.policy-modal');
                if (modal) modal.classList.add('hidden');
            });
        });

    // 3️⃣ Esc key closes any open modal
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            const open = document.querySelector('.policy-modal:not(.hidden)');
            if (open) open.classList.add('hidden');
        }
    });
});