/* static/js/modal.js -------------------------------------------------
   A tiny, dependency‑free modal loader.
   --------------------------------------------------------------- */

(() => {
  const modal = document.getElementById("global-modal");

  /* -----------------------------------------------------------------
       Helper – read a cookie (used for CSRF token)
       ----------------------------------------------------------------- */
  const getCookie = (name) => {
    const match = document.cookie.match(
      "(^|;)\\s*" + name + "\\s*=\\s*([^;]+)",
    );
    return match ? decodeURIComponent(match.pop()) : "";
  };

  /* -----------------------------------------------------------------
       Close the modal and clean its content
       ----------------------------------------------------------------- */
  const closeModal = () => {
    modal.classList.remove("open");
    modal.setAttribute("hidden", "");
    modal.innerHTML = "";
  };

  /* -----------------------------------------------------------------
       Attach close behaviour (backdrop click, ESC, X‑button)
       ----------------------------------------------------------------- */
  const bindCloseEvents = () => {
    // Click on backdrop or any element with data-close-modal
    modal.addEventListener("click", (e) => {
      if (
        e.target.dataset.closeModal !== undefined ||
        e.target.classList.contains("modal__backdrop")
      ) {
        closeModal();
      }
    });

    // Press ESC
    const escHandler = (e) => {
      if (e.key === "Escape") {
        closeModal();
        document.removeEventListener("keydown", escHandler);
      }
    };
    document.addEventListener("keydown", escHandler);
  };

  /* -----------------------------------------------------------------
       Turn a <form> inside the modal into an AJAX POST
       ----------------------------------------------------------------- */
  // ---------------------------------------------------------------
  // bindAjaxForm – turn a <form> inside the modal into an AJAX POST
  // ---------------------------------------------------------------
  const bindAjaxForm = (form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const action = form.action;
      const method = form.method.toUpperCase();

      const formData = new FormData(form);
      const csrf = getCookie("csrftoken");

      const response = await fetch(action, {
        method,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf,
        },
        credentials: "same-origin",
        body: formData,
      });

      const data = await response.json();

      // ---------- NEW LOGIC -------------------------------------------------
      // If the server tells us to go somewhere, make sure we keep the current
      // hash (unless the supplied URL already contains its own hash).
      // If there is no redirect we simply reload – the hash is automatically
      // preserved by `location.reload()`.
      // ----------------------------------------------------------------------
      if (data.success && data.redirect) {
        const currentHash = window.location.hash;
        let target = data.redirect;

        // Only append the hash when the target URL does NOT already have one.
        if (currentHash && !target.includes("#")) {
          // Preserve any trailing slash before we add the hash.
          target = target.replace(/\/?$/, "") + currentHash;
        }
        window.location.href = target;
      } else {
        // For safety, reload the page if something went wrong.
        // The hash stays intact because we reload the *same* URL.
        window.location.reload();
      }
    });
  };

  /* -----------------------------------------------------------------
       Load modal content from a URL that returns JSON {html: …}
       ----------------------------------------------------------------- */
  const openModalFromUrl = async (url) => {
    try {
      const resp = await fetch(url, {
        method: "GET",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      });

      if (!resp.ok) throw new Error("Network error");

      const data = await resp.json();
      if (!data.html) throw new Error("No HTML payload");

      // Inject the HTML and open the modal
      modal.innerHTML = data.html.trim();
      modal.removeAttribute("hidden");
      modal.classList.add("open");

      // Give focus to the first focusable element inside the dialog
      const focusable =
        modal.querySelector("[autofocus]") ||
        modal.querySelector(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
      focusable && focusable.focus();

      // Wire things up
      bindCloseEvents();

      // If there's a form (logout, delete, etc.) attach AJAX submit
      const modalForm = modal.querySelector("form[data-modal-form]");
      if (modalForm) bindAjaxForm(modalForm);
    } catch (err) {
      console.error("Modal load failed", err);
    }
  };

  /* -----------------------------------------------------------------
       Attach click listeners to any element with .js-modal‑trigger.
       We use event delegation so that elements added later by the
       AJAX widgets are automatically handled.
       ----------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    // The listener is attached to the <body> (or document) once.
    // Whenever a click bubbles up, we check whether the original
    // target (or one of its ancestors) has the class
    // “js-modal-trigger”.  This works for links, buttons, etc.
    document.body.addEventListener("click", (e) => {
      const trigger = e.target.closest(".js-modal-trigger");
      if (!trigger) return; // not a modal link

      e.preventDefault(); // stop normal navigation

      const url = trigger.dataset.url || trigger.getAttribute("href");
      if (url) {
        openModalFromUrl(url);
      }
    });
  });
})();
