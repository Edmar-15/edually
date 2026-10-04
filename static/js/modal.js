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
      e.stopImmediatePropagation();

      const fileInput = form.querySelector('input[type="file"]');
      const file = fileInput?.files[0];
      if (file) {
        const allowedExtensions = (fileInput.accept || "")
          .split(",")
          .map((extension) => extension.trim().toLowerCase())
          .filter(Boolean);
        const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
        if (!allowedExtensions.includes(extension)) {
          window.showGlobalToast(
            "Unsupported file type. Please choose a PDF, DOC, DOCX, PPT, or PPTX file.",
            "error"
          );
          return;
        }
        if (file.size > 10 * 1024 * 1024) {
          window.showGlobalToast(
            "File is too large. The maximum allowed size is 10 MB.",
            "error"
          );
          return;
        }
      }

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

      const data =
        response.status === 413
          ? { error: "File is too large. The maximum allowed size is 10 MB." }
          : await response.json().catch(() => ({
              error: "The upload could not be processed. Check the file and try again.",
            }));

      if (!data.success) {
        if (data.html) {
          modal.innerHTML = data.html.trim();
          modal.removeAttribute("hidden");
          modal.classList.add("open");
          bindCloseEvents();
          const newForm = modal.querySelector("form[data-modal-form]");
          if (newForm) bindAjaxForm(newForm);
        } else if (data.error) {
          window.showGlobalToast(data.error, "error");
        }
        return;
      }

      if (data.success && data.redirect) {
        const currentHash = window.location.hash;
        let target = data.redirect;

        if (data.message) {
          sessionStorage.setItem(
            "eduallyToastMessage",
            JSON.stringify({
              message: data.message,
              type: data.toastType || "success",
              duration: data.toastDuration || 4000,
            }),
          );
        }

        if (currentHash && !target.includes("#")) {
          target = target.replace(/\/?$/, "") + currentHash;
        }
        window.location.href = target;
        return;
      }

      if (data.message) {
        sessionStorage.setItem(
          "eduallyToastMessage",
          JSON.stringify({
            message: data.message,
            type: data.toastType || "success",
            duration: data.toastDuration || 4000,
          }),
        );
      }
      window.location.reload();
    });
  };

  /* -----------------------------------------------------------------
       Load modal content from a URL that returns JSON {html: …}
       ----------------------------------------------------------------- */
  const openModalFromUrl = async (url, trigger) => {
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

      if (trigger?.classList.contains("forum-push-button")) {
        document.querySelectorAll(".forum-push-button").forEach((button) => {
          button.querySelector(".forum-notification-badge")?.remove();
          button.setAttribute("aria-label", "View forum notifications");
        });
      }

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
        openModalFromUrl(url, trigger);
      }
    });
  });

  /* -----------------------------------------------------------------
   Confirmation modal
   ----------------------------------------------------------------- */

  const confirmModal = ({
    title = "Confirm Action",
    message = "Are you sure?",
    confirmText = "Confirm",
    cancelText = "Cancel",
  } = {}) => {
    return new Promise((resolve) => {
      if (!modal) {
        resolve(false);
        return;
      }

      modal.innerHTML = `
      <div class="modal__backdrop" data-close-modal></div>

      <div class="modal__dialog" role="alertdialog"
           aria-modal="true"
           aria-labelledby="global-confirm-title"
           aria-describedby="global-confirm-message">

        <div class="modal__header">
          <h2 id="global-confirm-title">${title}</h2>

          <button type="button"
                  class="modal__close"
                  data-close-modal
                  aria-label="Close">
            &times;
          </button>
        </div>

        <div class="modal__body">
          <p id="global-confirm-message">${message}</p>
        </div>

        <div class="modal__footer">
          <button type="button"
                  class="button button--secondary"
                  data-confirm-cancel>
            ${cancelText}
          </button>

          <button type="button"
                  class="button button--danger"
                  data-confirm-ok>
            ${confirmText}
          </button>
        </div>

      </div>
    `;

      modal.removeAttribute("hidden");
      modal.classList.add("open");

      const cleanup = (result) => {
        modal.classList.remove("open");
        modal.setAttribute("hidden", "");
        modal.innerHTML = "";
        document.removeEventListener("keydown", onKeyDown);
        resolve(result);
      };

      const onKeyDown = (e) => {
        if (e.key === "Escape") {
          cleanup(false);
        }
      };

      modal
        .querySelector("[data-confirm-ok]")
        ?.addEventListener("click", () => {
          cleanup(true);
        });

      modal
        .querySelector("[data-confirm-cancel]")
        ?.addEventListener("click", () => {
          cleanup(false);
        });

      modal.querySelectorAll("[data-close-modal]").forEach((element) => {
        element.addEventListener("click", () => {
          cleanup(false);
        });
      });

      document.addEventListener("keydown", onKeyDown);

      modal.querySelector("[data-confirm-cancel]")?.focus();
    });
  };

  window.confirmModal = confirmModal;
})();
