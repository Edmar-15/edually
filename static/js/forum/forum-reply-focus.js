document.addEventListener('DOMContentLoaded', function() {
    const params = new URLSearchParams(window.location.search);
    const focusReply = params.get('focus_reply');
    if (!focusReply) return;

    const el = document.querySelector(`[data-reply-id='${focusReply}']`);
    if (!el) return;

    el.classList.add('highlight');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Remove highlight after 4 seconds
    setTimeout(() => {
        el.classList.remove('highlight');
    }, 4000);
});
