document.addEventListener('DOMContentLoaded', () => {
  const body = document.body;
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.querySelector('.main-content');

  if (!sidebar || !mainContent) {
    return;
  }

  body.classList.add('SidebarProvider');
  mainContent.classList.add('SidebarInset');

  let trigger = document.querySelector('.sidebar-trigger');
  if (!trigger) {
    const sidebarHeader = document.querySelector('.sidebar-header');
    if (!sidebarHeader) {
      return;
    }

    trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'sidebar-trigger';
    trigger.setAttribute('aria-controls', 'sidebar');
    trigger.setAttribute('aria-expanded', 'true');
    trigger.setAttribute('aria-label', 'Collapse navigation sidebar');
    trigger.innerHTML = '<span class="sr-only">Toggle sidebar</span><svg class="sidebar-trigger-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    sidebarHeader.insertBefore(trigger, sidebarHeader.firstChild);
  }

  const setExpandedState = (isExpanded) => {
    trigger.setAttribute('aria-expanded', String(isExpanded));
    trigger.setAttribute('aria-label', isExpanded ? 'Collapse navigation sidebar' : 'Expand navigation sidebar');
  };

  const STORAGE_KEY = 'eduallySidebarState';
  let isAnimating = false;

  const applyState = (isCollapsed) => {
    body.classList.toggle('sidebar-collapsed', isCollapsed);
    setExpandedState(!isCollapsed);
  };

  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'collapsed') {
      applyState(true);
    }
  } catch (error) {
    // Ignore storage errors in restricted environments.
  }

  const handleToggle = () => {
    if (isAnimating) {
      return;
    }

    isAnimating = true;
    trigger.disabled = true;
    body.classList.add('sidebar-animating');

    const shouldCollapse = !body.classList.contains('sidebar-collapsed');
    applyState(shouldCollapse);

    const onEnd = (event) => {
      if (event.target !== sidebar) {
        return;
      }

      const prop = event.propertyName || '';
      if (prop && !/width|transform|padding|margin-left|opacity/.test(prop)) {
        return;
      }

      sidebar.removeEventListener('transitionend', onEnd);
      body.classList.remove('sidebar-animating');
      trigger.disabled = false;
      isAnimating = false;
    };

    sidebar.addEventListener('transitionend', onEnd);

    window.setTimeout(() => {
      if (isAnimating) {
        body.classList.remove('sidebar-animating');
        trigger.disabled = false;
        isAnimating = false;
        try {
          sidebar.removeEventListener('transitionend', onEnd);
        } catch (error) {
          // Ignore cleanup errors.
        }
      }
    }, 350);

    try {
      localStorage.setItem(STORAGE_KEY, shouldCollapse ? 'collapsed' : 'expanded');
    } catch (error) {
      // Ignore storage errors.
    }
  };

  trigger.addEventListener('click', handleToggle);
});
