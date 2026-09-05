/**
 * Floating Labels Animation
 * Handles smooth floating label animation for form inputs and selects
 */

document.addEventListener('DOMContentLoaded', function () {
    const formGroups = document.querySelectorAll('.floating-label-group');

    formGroups.forEach(group => {
        const field = group.querySelector('input, select');
        const label = group.querySelector('label');

        if (!field || !label) return;

        function updateValueState() {
            if (field.value) {
                group.classList.add('has-value');
            } else {
                group.classList.remove('has-value');
            }
        }

        // Handle focus
        field.addEventListener('focus', function () {
            group.classList.add('focused');
        });

        // Handle blur
        field.addEventListener('blur', function () {
            group.classList.remove('focused');
            updateValueState();
        });

        // Handle typing for inputs
        field.addEventListener('input', function () {
            updateValueState();
        });

        // Handle selection changes for select
        field.addEventListener('change', function () {
            updateValueState();
        });

        // Set initial state
        updateValueState();

        if (field.value) {
            group.classList.add('has-value');
        }
    });
});