document.addEventListener('DOMContentLoaded', function() {
    const toggleButtons = document.querySelectorAll('.toggle-password');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const passwordInput = this.parentElement.querySelector('input[type="password"], input[type="text"]');
            
            if (!passwordInput) return;
            
            const wrapper = this.closest('.password-input-wrapper');
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                if (wrapper) wrapper.classList.add('password-visible');
            } else {
                passwordInput.type = 'password';
                if (wrapper) wrapper.classList.remove('password-visible');
            }
        });
    });
});
