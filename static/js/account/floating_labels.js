/**
 * Floating Labels Animation
 * Handles smooth floating label animation for form inputs
 */

document.addEventListener('DOMContentLoaded', function() {
    const formGroups = document.querySelectorAll('.floating-label-group');

    formGroups.forEach(group => {
        const input = group.querySelector('input');
        const label = group.querySelector('label');

        if (!input || !label) return;

        // Handle focus event
        input.addEventListener('focus', function() {
            group.classList.add('focused');
        });

        // Handle blur event
        input.addEventListener('blur', function() {
            if (!input.value) {
                group.classList.remove('focused');
            }
        });

        // Handle input event
        input.addEventListener('input', function() {
            if (input.value) {
                group.classList.add('has-value');
            } else {
                group.classList.remove('has-value');
            }
        });

        // Set initial state if input has value on page load
        if (input.value) {
            group.classList.add('has-value', 'focused');
        }
    });
});
