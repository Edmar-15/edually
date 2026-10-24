// Shared visibility control, including AJAX-loaded password forms.
document.addEventListener('click', function (event) {
    const button = event.target.closest('.toggle-password');
    if (!button) return;

    const wrapper = button.closest('.password-input-wrapper');
    const input = wrapper?.querySelector('input[type="password"], input[type="text"]');
    if (!input) return;

    event.preventDefault();
    const showPassword = input.type === 'password';
    input.type = showPassword ? 'text' : 'password';
    wrapper.classList.toggle('password-visible', showPassword);
    button.setAttribute('aria-label', showPassword ? 'Hide password' : 'Show password');
    button.setAttribute('aria-pressed', String(showPassword));
});
