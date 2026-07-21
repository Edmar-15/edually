/**
 * Form Validation
 * Client-side validation for login and register forms
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    if (!form) return;

    const inputs = form.querySelectorAll('input[type="text"], input[type="email"], input[type="password"]');
    const submitButton = form.querySelector('button[type="submit"]');

    // Add validation listeners
    inputs.forEach(input => {
        input.addEventListener('blur', validateInput);
        input.addEventListener('input', validateInput);
    });

    // Prevent form submission if invalid
    form.addEventListener('submit', function(e) {
        let isValid = true;
        inputs.forEach(input => {
            if (!validateInput.call(input)) {
                isValid = false;
            }
        });

        if (!isValid) {
            e.preventDefault();
        }
    });

    function validateInput() {
        const input = this;
        const group = input.closest('.floating-label-group') || input.closest('.input-group') || input.closest('.form-group');
        const errorMsg = group ? group.querySelector('.validation-error') : null;

        let isValid = true;
        let errorText = '';

        // Email validation
        if (input.type === 'email' || input.name.includes('email')) {
            if (!input.value.trim()) {
                isValid = false;
                errorText = 'Email is required';
            } else if (!isValidEmail(input.value)) {
                isValid = false;
                errorText = 'Please enter a valid email address';
            }
        }

        // Password validation
        if (input.type === 'password') {
            if (!input.value.trim()) {
                isValid = false;
                errorText = 'Password is required';
            } else if (input.name === 'password1' && !isPasswordStrong(input.value)) {
                isValid = false;
                errorText = 'Password must be at least 12 characters, include a number, a special character, and have the first letter uppercase.';
            }

            // Check if confirm password matches
            if (input.name.includes('password2')) {
                const password1 = form.querySelector('input[name="password1"]');
                if (password1 && input.value !== password1.value) {
                    isValid = false;
                    errorText = 'Passwords do not match';
                }
            }
        }

        // Username validation
        if (input.name === 'username' && input.closest('form').querySelector('input[name="email"]')) {
            // Register form
            if (!input.value.trim()) {
                isValid = false;
                errorText = 'Username is required';
            } else if (input.value.length < 3) {
                isValid = false;
                errorText = 'Username must be at least 3 characters';
            }
        }

        // Required fields
        if (input.hasAttribute('required') && !input.value.trim()) {
            isValid = false;
            errorText = errorText || input.placeholder || 'This field is required';
        }

        // Update UI
        if (group) {
            if (isValid) {
                group.classList.remove('input-error');
                group.classList.add('input-valid');
                if (errorMsg) errorMsg.remove();
            } else {
                group.classList.remove('input-valid');
                group.classList.add('input-error');
                
                // Remove old error message if exists
                const oldError = group.querySelector('.validation-error');
                if (oldError) oldError.remove();

                // Add new error message
                if (errorText) {
                    const errorElement = document.createElement('div');
                    errorElement.className = 'validation-error';
                    errorElement.textContent = errorText;
                    group.appendChild(errorElement);
                }
            }
        }

        return isValid;
    }

    function updatePasswordStrength() {
        const value = this.value || '';
        const strengthMeter = form.querySelector('.strength-meter');
        const strengthLabel = form.querySelector('#password-strength-label');
        const passed = [
            value.length >= 12,
            /^[A-Z]/.test(value),
            /\d/.test(value),
            /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>\/\?~`]/.test(value),
        ].filter(Boolean).length;

        const state = passed === 4 ? 'strong' : passed === 3 ? 'medium' : passed >= 2 ? 'weak' : 'very-weak';
        const labels = {
            'very-weak': 'Very weak',
            'weak': 'Weak',
            'medium': 'Medium',
            'strong': 'Strong',
        };

        if (strengthMeter) {
            strengthMeter.classList.remove('very-weak', 'weak', 'medium', 'strong');
            strengthMeter.classList.add(state);
        }
        if (strengthLabel) {
            strengthLabel.textContent = labels[state];
        }
    }

    function isFirstAlphabeticUppercase(value) {
        const match = value.match(/[A-Za-z]/);
        return match ? match[0] === match[0].toUpperCase() : false;
    }

    function isPasswordStrong(value) {
        return value.length >= 12 &&
            isFirstAlphabeticUppercase(value) &&
            /\d/.test(value) &&
            /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>\/\?~`]/.test(value);
    }

    if (form) {
        const password1 = form.querySelector('input[name="password1"]');
        if (password1) {
            password1.addEventListener('input', updatePasswordStrength);
            password1.addEventListener('blur', updatePasswordStrength);
            updatePasswordStrength.call(password1);
        }
    }

    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
});
