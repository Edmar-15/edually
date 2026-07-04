document.addEventListener('DOMContentLoaded', () => {
  const body = document.body;
  body.classList.add('SidebarProvider');

  const sidebar = document.getElementById('sidebar');
  const mainContent = document.querySelector('.main-content');

  if (!sidebar || !mainContent) {
    return;
  }

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
    trigger.innerHTML = '<span class="sr-only">Toggle sidebar</span><i class="fas fa-bars" aria-hidden="true"></i>';
    sidebarHeader.insertBefore(trigger, sidebarHeader.firstChild);
  }

  const setExpandedState = (isExpanded) => {
    trigger.setAttribute('aria-expanded', String(isExpanded));
    trigger.setAttribute('aria-label', isExpanded ? 'Collapse navigation sidebar' : 'Expand navigation sidebar');
  };

  const STORAGE_KEY = 'eduallySidebarState';
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'collapsed') {
      body.classList.add('sidebar-collapsed');
      setExpandedState(false);
    }
  } catch (error) {
    // Ignore storage errors in restricted environments.
  }

  // Prevent rapid double-toggles by ignoring clicks while animating.
  let isAnimating = false;

  const handleToggle = () => {
    if (isAnimating) return;
    isAnimating = true;

    // reflect new state immediately for screen readers
    const collapsed = body.classList.toggle('sidebar-collapsed');
    setExpandedState(!collapsed);

    // disable the trigger to avoid extra clicks
    trigger.disabled = true;
    body.classList.add('sidebar-animating');

    // Listen for the sidebar transition end; only respond when target is the sidebar
    const onEnd = (ev) => {
      if (ev.target !== sidebar) return;
      // Only consider relevant properties to avoid multiple callbacks
      const prop = ev.propertyName || '';
      if (prop && !/width|transform|padding/.test(prop)) return;
      sidebar.removeEventListener('transitionend', onEnd);
      body.classList.remove('sidebar-animating');
      trigger.disabled = false;
      isAnimating = false;
    };

    sidebar.addEventListener('transitionend', onEnd);

    // Fallback: ensure we re-enable if transitionend doesn't fire
    setTimeout(() => {
      if (isAnimating) {
        body.classList.remove('sidebar-animating');
        trigger.disabled = false;
        isAnimating = false;
        try {
          sidebar.removeEventListener('transitionend', onEnd);
        } catch (e) {}
      }
    }, 600);

    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? 'collapsed' : 'expanded');
    } catch (error) {
      // Ignore storage errors.
    }
  };

  trigger.addEventListener('click', handleToggle);
});
