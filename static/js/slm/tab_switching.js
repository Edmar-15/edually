document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".tabs").forEach((container) => {
    const tabs = container.querySelectorAll('[role="tab"]');
    const panels = container.querySelectorAll('[role="tabpanel"]');

    if (!tabs.length || !panels.length) {
      return;
    }

    const storageKey = `activeTab_${container.id || "default"}`;

    const activate = (newIdx, moveFocus = false) => {
      if (newIdx < 0 || newIdx >= tabs.length) {
        return;
      }

      tabs.forEach((tab, index) => {
        const isActive = index === newIdx;

        tab.setAttribute("aria-selected", String(isActive));
        tab.setAttribute("tabindex", isActive ? "0" : "-1");
        tab.classList.toggle("active", isActive);

        const desc = tab.querySelector(".tab-desc");

        if (desc) {
          desc.setAttribute("aria-hidden", String(!isActive));
        }
      });

      panels.forEach((panel, index) => {
        const isActive = index === newIdx;

        panel.hidden = !isActive;
        panel.setAttribute("aria-hidden", String(!isActive));
      });

      try {
        localStorage.setItem(storageKey, String(newIdx));
      } catch (error) {
        // Tabs still work if storage is unavailable.
      }

      if (moveFocus) {
        try {
          tabs[newIdx].focus({ preventScroll: true });
        } catch (error) {
          tabs[newIdx].focus();
        }
      }
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => {
        activate(index, true);
      });
    });

    container.addEventListener("keydown", (event) => {
      const currentIndex = Array.from(tabs).findIndex(
        (tab) => tab.getAttribute("aria-selected") === "true",
      );

      if (currentIndex < 0) {
        return;
      }

      let nextIndex = null;

      switch (event.key) {
        case "ArrowRight":
          nextIndex = (currentIndex + 1) % tabs.length;
          break;

        case "ArrowLeft":
          nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
          break;

        case "Home":
          nextIndex = 0;
          break;

        case "End":
          nextIndex = tabs.length - 1;
          break;

        default:
          return;
      }

      event.preventDefault();

      activate(nextIndex, true);
    });

    let initialIndex = 0;
    const hashIndex = Array.from(tabs).findIndex(
      (tab) => tab.id === window.location.hash.slice(1),
    );

    if (hashIndex >= 0) {
      initialIndex = hashIndex;
    } else {
      try {
        const saved = Number(localStorage.getItem(storageKey));

        if (Number.isInteger(saved) && saved >= 0 && saved < tabs.length) {
          initialIndex = saved;
        }
      } catch (error) {
        initialIndex = 0;
      }
    }

    activate(initialIndex, false);
  });
});
