document.addEventListener('DOMContentLoaded', () => {
  const body = document.body;
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.querySelector('.main-content');

  if (!sidebar || !mainContent) {
    return;
  }

  body.classList.add('SidebarProvider');
  mainContent.classList.add('SidebarInset');

  const mobileBreakpoint = 768;
  const STORAGE_KEY = 'eduallySidebarState';
  let isAnimating = false;

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

  const backdrop = document.createElement('div');
  backdrop.className = 'sidebar-backdrop';
  body.appendChild(backdrop);

  const mobileTrigger = document.createElement('button');
  mobileTrigger.type = 'button';
  mobileTrigger.className = 'mobile-sidebar-trigger';
  mobileTrigger.setAttribute('aria-controls', 'sidebar');
  mobileTrigger.setAttribute('aria-expanded', 'false');
  mobileTrigger.setAttribute('aria-label', 'Open navigation sidebar');
  mobileTrigger.innerHTML = '<span class="sr-only">Toggle sidebar</span><svg class="sidebar-trigger-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  body.appendChild(mobileTrigger);

  const setExpandedState = (isExpanded) => {
    trigger.setAttribute('aria-expanded', String(isExpanded));
    trigger.setAttribute('aria-label', isExpanded ? 'Collapse navigation sidebar' : 'Expand navigation sidebar');
  };

  const saveDesktopState = (isCollapsed) => {
    try {
      localStorage.setItem(STORAGE_KEY, isCollapsed ? 'collapsed' : 'expanded');
    } catch (error) {
      // Ignore storage errors.
    }
  };

  const applyDesktopState = (isCollapsed) => {
    body.classList.toggle('sidebar-collapsed', isCollapsed);
    setExpandedState(!isCollapsed);
  };

  const closeMobileSidebar = () => {
    body.classList.remove('sidebar-mobile-open');
    sidebar.classList.remove('is-open');
    mobileTrigger.classList.remove('is-active');
    mobileTrigger.setAttribute('aria-expanded', 'false');
    mobileTrigger.setAttribute('aria-label', 'Open navigation sidebar');
    body.style.overflow = '';
  };

  const openMobileSidebar = () => {
    body.classList.add('sidebar-mobile-open');
    sidebar.classList.add('is-open');
    mobileTrigger.classList.add('is-active');
    mobileTrigger.setAttribute('aria-expanded', 'true');
    mobileTrigger.setAttribute('aria-label', 'Close navigation sidebar');
    body.style.overflow = 'hidden';
  };

  const syncLayout = () => {
    const isMobile = window.innerWidth < mobileBreakpoint;

    if (isMobile) {
      body.classList.remove('sidebar-collapsed');
      sidebar.classList.remove('is-open');
      mobileTrigger.style.display = 'inline-flex';
      backdrop.style.display = 'block';
      if (!body.classList.contains('sidebar-mobile-open')) {
        closeMobileSidebar();
      }
      return;
    }

    mobileTrigger.style.display = 'none';
    backdrop.style.display = 'none';
    closeMobileSidebar();

    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      applyDesktopState(saved === 'collapsed');
    } catch (error) {
      applyDesktopState(false);
    }
  };

  const toggleDesktopSidebar = () => {
    if (isAnimating) {
      return;
    }

    isAnimating = true;
    trigger.disabled = true;
    body.classList.add('sidebar-animating');

    const shouldCollapse = !body.classList.contains('sidebar-collapsed');
    applyDesktopState(shouldCollapse);

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

    saveDesktopState(shouldCollapse);
  };

  const handleToggle = () => {
    if (window.innerWidth < mobileBreakpoint) {
      if (body.classList.contains('sidebar-mobile-open')) {
        closeMobileSidebar();
      } else {
        openMobileSidebar();
      }
      return;
    }

    toggleDesktopSidebar();
  };

  trigger.addEventListener('click', handleToggle);
  mobileTrigger.addEventListener('click', handleToggle);
  backdrop.addEventListener('click', closeMobileSidebar);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && body.classList.contains('sidebar-mobile-open')) {
      closeMobileSidebar();
    }
  });

  window.addEventListener('resize', syncLayout);
  syncLayout();
});
