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

        field.addEventListener('focus', function () {
            group.classList.add('focused');
        });

        field.addEventListener('blur', function () {
            group.classList.remove('focused');
            updateValueState();
        });

        field.addEventListener('input', function () {
            updateValueState();
        });

        field.addEventListener('change', function () {
            updateValueState();
        });

        updateValueState();

        if (field.value) {
            group.classList.add('has-value');
        }
    });
});