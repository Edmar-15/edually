(function () {
    const key = 'eduallyDarkMode';
    const cookieName = 'eduallyTheme';
    const htmlEl = document.documentElement;

    function getCookie(name) {
        const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return match ? match.pop() : '';
    }

    function applyTheme(theme) {
        const isDark = theme === 'dark';
        htmlEl.classList.toggle('dark', isDark);
        htmlEl.dataset.theme = theme;

        const checkboxes = document.querySelectorAll('#dark-mode-toggle');
        checkboxes.forEach((checkbox) => {
            checkbox.checked = isDark;
        });

        document.querySelectorAll('[data-theme-toggle]').forEach((toggle) => {
            toggle.setAttribute('aria-pressed', String(isDark));
            toggle.classList.toggle('is-dark', isDark);

            const icon = toggle.querySelector('i');
            if (icon) {
                icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
            }

            const label = toggle.querySelector('.theme-toggle-label');
            if (label) {
                label.textContent = isDark ? 'Light Mode' : 'Dark Mode';
            }
        });
    }

    function persistTheme(theme) {
        try {
            localStorage.setItem(key, theme);
        } catch (error) {
            // ignore storage access errors
        }

        const csrf = getCookie('csrftoken');
        const url = '/account/api/set-theme/';

        fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf || ''
            },
            body: JSON.stringify({ theme })
        }).catch(() => {
            // ignore network errors and fall back to cookie-based persistence
        });

        document.cookie = cookieName + '=' + theme + '; path=/; max-age=31536000; SameSite=Lax';
    }

    function getSavedTheme() {
        const forcedTheme = htmlEl.dataset.forceTheme;
        if (forcedTheme === 'dark' || forcedTheme === 'light') {
            return forcedTheme;
        }

        try {
            const stored = localStorage.getItem(key);
            if (stored === 'dark' || stored === 'light') {
                return stored;
            }
        } catch (error) {
            // ignore storage access errors
        }

        const cookieTheme = getCookie(cookieName);
        if (cookieTheme === 'dark' || cookieTheme === 'light') {
            return cookieTheme;
        }

        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light';
    }

    const initialTheme = getSavedTheme();
    applyTheme(initialTheme);

    document.querySelectorAll('[data-theme-toggle]').forEach((toggle) => {
        toggle.addEventListener('click', () => {
            const nextTheme = htmlEl.classList.contains('dark') ? 'light' : 'dark';
            applyTheme(nextTheme);
            persistTheme(nextTheme);
        });
    });

    const checkbox = document.getElementById('dark-mode-toggle');
    if (checkbox) {
        checkbox.addEventListener('change', (event) => {
            const nextTheme = event.target.checked ? 'dark' : 'light';
            applyTheme(nextTheme);
            persistTheme(nextTheme);
        });
    }
})();
