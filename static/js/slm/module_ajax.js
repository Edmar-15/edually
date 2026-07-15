// ---------------------------------------------------------------
// module_ajax.js – Ajax widget for “Modules” of a Subject
// ---------------------------------------------------------------
import { csrftoken } from "./utils.js";

/**
 * Initialise the modules widget.
 *
 * Expected data‑attributes on the root element:
 *
 *   data-list-url           → "/slm/api/subjects/42/modules/"
 *   data-create-url         → "/slm/api/subjects/42/modules/create/"
 *   data-update-url         → "/slm/api/modules/0/"
 *   data-delete-url         → "/slm/api/modules/0/delete/"
 *   data-file-replace-url   → "/slm/api/modules/0/file/"
 */
export function initModuleWidget(rootEl) {
  /* -----------------------------------------------------------------
   * 1️⃣  URLs from data‑attributes – they contain the dummy “0”
   * ----------------------------------------------------------------- */
  const listUrl = rootEl.dataset.listUrl; // …?page=
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl; // “…/modules/0/”
  const deleteTpl = rootEl.dataset.deleteUrl; // “…/modules/0/delete/”
  const replaceFileTpl = rootEl.dataset.fileReplaceUrl; // “…/modules/0/file/”

  /* -----------------------------------------------------------------
   * Helper – replace the dummy “0” with a real id
   * ----------------------------------------------------------------- */
  const replaceId = (template, id) => template.replace(/0(?=\/|$)/, id);
  // The RegExp looks for a `0` that is either at the very end of the string
  // or just before a slash – this prevents accidental replacement of a
  // `0` that could appear in a query‑string or elsewhere.

  /* -----------------------------------------------------------------
   * 2️⃣  Toast helper -------------------------------------------------
   * ----------------------------------------------------------------- */
  /**
   * Lazily get (or create) the toast container element.
   * The container lives in the corner of the page (see CSS) and has
   * `aria-live="polite"` so screen‑readers announce its content.
   */
  const getToastContainer = () => {
    // 1️⃣  Look for a container that is a direct descendant of the widget.
    let container = rootEl.querySelector(".toast-container");
    // 2️⃣  If the developer omitted it, create a new one *inside* the widget.
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container";
      container.setAttribute("aria-live", "polite");
      rootEl.appendChild(container);
    }
    return container;
  };
  const $toastContainer = getToastContainer();

  /**
   * Show a toast.
   *
   * @param {string} message   Text to display.
   * @param {'success'|'error'|'info'|'warning'} [type='info']   Visual variant.
   * @param {number} [duration=4000]   How long the toast stays (ms).
   */
  const showToast = (message, type = "info", duration = 4000) => {
    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    // CSS animation reads this custom property to know when to start fade‑out
    toast.style.setProperty("--toast-life", `${duration}ms`);

    // Use a tiny emoji as an icon – you could replace these with SVGs later.
    const icon = document.createElement("span");
    icon.className = "toast__icon";
    if (type === "success") icon.textContent = "";
    else if (type === "error") icon.textContent = "";
    else if (type === "warning") icon.textContent = "";
    else icon.textContent = "";

    const msg = document.createElement("span");
    msg.textContent = message;

    toast.appendChild(icon);
    toast.appendChild(msg);

    // Clicking a toast dismisses it instantly.
    toast.addEventListener("click", () => toast.remove());

    $toastContainer.appendChild(toast);

    // Auto‑remove after the requested lifetime plus a little extra for the fade‑out.
    setTimeout(() => toast.remove(), duration + 500);
  };

  /* -----------------------------------------------------------------
   * 3️⃣  DOM shortcuts (all inside the widget)
   * ----------------------------------------------------------------- */
  const $list = rootEl.querySelector("#module-list");
  if (!$list) {
    console.warn("Module widget is missing #module-list container.");
    return;
  }

  const $numInput = rootEl.querySelector("#module-number-input");
  const $nameInput = rootEl.querySelector("#module-name-input");
  const $fileInput = rootEl.querySelector("#module-file-input");
  const $addBtn = rootEl.querySelector("#module-add-btn");
  const $editModal = rootEl.querySelector("#module-edit-modal");
  const $deleteModal = rootEl.querySelector("#module-delete-modal");

  function getModuleIconMarkup(fileUrl = "") {
    const ext = (fileUrl || "")
      .split("?")[0]
      .split("#")[0]
      .split(".")
      .pop()
      ?.toLowerCase();

    switch (ext) {
      case "pdf":
        return '<i class="fas fa-file-pdf" aria-hidden="true"></i>';
      case "doc":
      case "docx":
        return '<i class="fas fa-file-word" aria-hidden="true"></i>';
      case "ppt":
      case "pptx":
        return '<i class="fas fa-file-powerpoint" aria-hidden="true"></i>';
      default:
        return '<i class="fas fa-file-alt" aria-hidden="true"></i>';
    }
  }

  function getModuleIconClass(fileUrl = "") {
    const ext = (fileUrl || "")
      .split("?")[0]
      .split("#")[0]
      .split(".")
      .pop()
      ?.toLowerCase();

    switch (ext) {
      case "pdf":
        return "pm-card__icon--pdf";
      case "doc":
      case "docx":
        return "pm-card__icon--doc";
      case "ppt":
      case "pptx":
        return "pm-card__icon--ppt";
      default:
        return "";
    }
  }

  /* -----------------------------------------------------------------
   * 4️⃣  Render a single module card – mirrors the pm‑card UI
   * ----------------------------------------------------------------- */
  function renderCard(mod) {
    // ---- Card container -------------------------------------------------
    const card = document.createElement("div");
    card.className = "pm-card";
    card.dataset.id = mod.id;

    // ---- Header (icon + title) -----------------------------------------
    const header = document.createElement("div");
    header.className = "pm-card__header";

    const iconWrap = document.createElement("div");
    iconWrap.className =
      `pm-card__icon ${getModuleIconClass(mod.file_url)}`.trim();
    iconWrap.innerHTML = getModuleIconMarkup(mod.file_url);
    header.appendChild(iconWrap);

    const content = document.createElement("div");
    content.className = "pm-card__content";

    const title = document.createElement("h3");
    title.textContent = `#${mod.module_number} – ${mod.module_name}`;
    content.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "pm-card__meta";

    const typePill = document.createElement("span");
    typePill.className = "pm-card__pill";
    const fileName = mod.file_url ? mod.file_url.split("/").pop() : "Document";
    const ext = fileName.includes(".")
      ? fileName.split(".").pop().toUpperCase()
      : "FILE";
    typePill.textContent = ext;
    meta.appendChild(typePill);

    content.appendChild(meta);
    header.appendChild(content);
    card.appendChild(header);

    // -----------------------------------------------------------------
    // Actions – identical layout to the Personal‑Material widget
    // -----------------------------------------------------------------
    const actions = document.createElement("div");
    actions.className = "pm-card__actions";

    // View button – links to the module detail page
    const viewBtn = document.createElement("a");
    viewBtn.href = `/slm/subjects/${mod.subject_id}/modules/${mod.id}/`;
    viewBtn.className = "button button-plain";
    viewBtn.textContent = "View";
    viewBtn.title = "Open module preview";
    actions.appendChild(viewBtn);

    // Owner‑only edit / delete
    if (mod.is_owner) {
      // ---- Edit ---------------------------------------------------------
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.title = "Edit";
      editBtn.className = "pm-card__action";
      editBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      editBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openEditModal(mod);
      });
      actions.appendChild(editBtn);

      // ---- Delete -------------------------------------------------------
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.title = "Delete";
      delBtn.className = "pm-card__action pm-card__action--delete";
      delBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
      delBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openDeleteModal(mod.id);
      });
      actions.appendChild(delBtn);
    }

    card.appendChild(actions);
    return card;
  }

  /* -----------------------------------------------------------------
   * 5️⃣  Paginator – unchanged copy‑paste from subject widget
   * ----------------------------------------------------------------- */
  function renderPaginator(meta) {
    const old = rootEl.querySelector(".paginator");
    if (old) old.remove();

    const nav = document.createElement("nav");
    nav.className = "paginator";
    nav.setAttribute("aria-label", "Modules pagination");

    const ul = document.createElement("ul");
    ul.className = "paginator__list";
    nav.appendChild(ul);

    const makeItem = (
      label,
      targetPage = null,
      disabled = false,
      current = false,
      ellipsis = false,
    ) => {
      const li = document.createElement("li");
      li.className = "paginator__item";
      if (disabled) li.classList.add("paginator__item--disabled");
      if (current) li.classList.add("paginator__item--current");
      if (ellipsis) li.classList.add("paginator__item--ellipsis");

      if (current || ellipsis) {
        const span = document.createElement("span");
        span.className = "paginator__link";
        span.textContent = label;
        li.appendChild(span);
        return li;
      }

      const a = document.createElement("a");
      a.className = "paginator__link";
      a.href = "#";
      a.textContent = label;
      if (disabled) a.setAttribute("tabindex", "-1");
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const page = targetPage !== null ? targetPage : Number(label);
        if (!isNaN(page) && page !== meta.page) load(page);
      });
      li.appendChild(a);
      return li;
    };

    ul.appendChild(
      makeItem("←", meta.previous_page_number, !meta.has_previous),
    );
    ul.appendChild(makeItem("1", null, false, meta.page === 1));
    if (meta.page - 2 > 2)
      ul.appendChild(makeItem("…", null, false, false, true));

    const start = Math.max(2, meta.page - 1);
    const end = Math.min(meta.total_pages - 1, meta.page + 1);
    for (let i = start; i <= end; i++) {
      if (i !== 1 && i !== meta.total_pages) {
        ul.appendChild(makeItem(String(i), null, false, meta.page === i));
      }
    }

    if (meta.page + 2 < meta.total_pages - 1)
      ul.appendChild(makeItem("…", null, false, false, true));
    if (meta.total_pages > 1) {
      ul.appendChild(
        makeItem(
          String(meta.total_pages),
          null,
          false,
          meta.page === meta.total_pages,
        ),
      );
    }
    ul.appendChild(makeItem("→", meta.next_page_number, !meta.has_next));

    $list.parentNode.appendChild(nav);
  }

  /* -----------------------------------------------------------------
   * 6️⃣  LOAD – fetch a page and render
   * ----------------------------------------------------------------- */
  async function load(page = 1) {
    try {
      const resp = await fetch(`${listUrl}?page=${page}`, {
        credentials: "same-origin",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const payload = await resp.json();

      // ---- render cards -------------------------------------------------
      const data = payload.results;
      if (!data.length) {
        const existingEmpty = $list.querySelector(".module-empty-state");
        if (!existingEmpty) {
          $list.innerHTML = `
            <section class="module-empty-state" aria-live="polite">
              <div class="module-empty-state__icon"><i class="fa-solid fa-book"></i></div>
              <h3>No modules here yet</h3>
              <p>Share your first learning material and make this subject feel ready to study.</p>
            </section>
          `;
        }
        const old = rootEl.querySelector(".paginator");
        if (old) old.remove();
        return;
      }

      $list.innerHTML = "";
      let row;
      data.forEach((mod, idx) => {
        if (idx % 4 === 0) {
          row = document.createElement("div");
          row.className = "module-row";
          $list.appendChild(row);
        }
        row.appendChild(renderCard(mod));
      });

      // ---- paginator ----------------------------------------------------
      renderPaginator(payload);
    } catch (e) {
      showToast(`Failed to load modules – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 7️⃣  CREATE – POST a new module (multipart/form‑data)
   * ----------------------------------------------------------------- */
  async function create() {
    if (!$numInput || !$nameInput || !$fileInput) return;

    const form = new FormData();
    form.append("module_number", $numInput.value.trim());
    form.append("module_name", $nameInput.value.trim());

    const file = $fileInput.files[0];
    if (file) {
      const ALLOWED_EXT = [".pdf", ".doc", ".docx", ".ppt", ".pptx"];
      const name = file.name.toLowerCase();
      if (!ALLOWED_EXT.some((ext) => name.endsWith(ext))) {
        showToast(
          "Only PDF, Word (.doc/.docx) and PowerPoint (.ppt/.pptx) files are allowed.",
          "error",
        );
        return;
      }
      form.append("file", file);
    }

    try {
      const resp = await fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrftoken },
        body: form,
      });

      if (resp.status === 201) {
        showToast("Module created", "success");
        $numInput.value = "";
        $nameInput.value = "";
        $fileInput.value = "";
        load();
      } else {
        const err = await resp.json();
        showToast(err.error || resp.statusText, "error");
      }
    } catch (e) {
      showToast(`Failed to create module – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 8️⃣  EDIT – open edit modal (HTML already lives in the template)
   * ----------------------------------------------------------------- */
  function openEditModal(mod) {
    // Store the id of the module we are editing – used by the submit handler
    $editModal.dataset.modId = mod.id;

    // Pre‑fill the fields
    const form = $editModal.querySelector("#modal-edit-form");
    if (form) {
      form.module_number.value = mod.module_number;
      form.module_name.value = mod.module_name;
      form.file.value = "";
    }

    $editModal.classList.remove("hidden");
  }

  /* -----------------------------------------------------------------
   * NEW – open delete confirmation modal
   * ----------------------------------------------------------------- */
  function openDeleteModal(pk) {
    $deleteModal.dataset.modId = pk;
    $deleteModal.classList.remove("hidden");
  }

  /* -----------------------------------------------------------------
   * 9️⃣  DELETE – actually send the DELETE request.
   * ----------------------------------------------------------------- */
  async function performDelete(pk) {
    const url = replaceId(deleteTpl, pk);
    try {
      const resp = await fetch(url, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrftoken },
      });
      if (resp.status === 204) {
        showToast("Deleted", "success");
        load();
      } else {
        const err = await resp.json();
        showToast(err.error || resp.statusText, "error");
      }
    } catch (e) {
      showToast(`Failed to delete module – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 🔟  UI bindings & modal handling
   * ----------------------------------------------------------------- */
  if ($addBtn) $addBtn.addEventListener("click", create);

  // ---- Edit modal – cancel & submit ----
  if ($editModal) {
    const cancelBtn = $editModal.querySelector("#modal-cancel");
    cancelBtn?.addEventListener("click", () =>
      $editModal.classList.add("hidden"),
    );

    const editForm = $editModal.querySelector("#modal-edit-form");
    editForm?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.target;
      const number = form.module_number.value.trim();
      const name = form.module_name.value.trim();
      const file = form.file.files[0];

      const payload = {};
      if (number) payload.module_number = number;
      if (name) payload.module_name = name;

      const modId = $editModal.dataset.modId;
      if (!modId) {
        showToast("No module selected for update.", "error");
        return;
      }

      const updateUrl = replaceId(updateTpl, modId);
      try {
        const resp = await fetch(updateUrl, {
          method: "PUT",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken,
          },
          body: JSON.stringify(payload),
        });

        if (!resp.ok) {
          const err = await resp.json();
          showToast(err.error || resp.statusText, "error");
          return;
        }

        // If a new file was provided, upload it via the dedicated endpoint
        if (file) {
          const replaceUrl = replaceId(replaceFileTpl, modId);
          const fileForm = new FormData();
          fileForm.append("file", file);
          const fileResp = await fetch(replaceUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrftoken },
            body: fileForm,
          });
          if (!fileResp.ok) {
            const ferr = await fileResp.json();
            showToast(
              `File replace failed – ${ferr.error || fileResp.statusText}`,
              "error",
            );
            return;
          }
        }

        showToast("Module updated", "success");
        $editModal.classList.add("hidden");
        load(); // refresh the list
      } catch (err) {
        showToast(`Failed to update module – ${err}`, "error");
      }
    });
  }

  // ---- Delete modal – cancel & confirm ----
  if ($deleteModal) {
    const cancelBtn = $deleteModal.querySelector("#modal-delete-cancel");
    cancelBtn?.addEventListener("click", () =>
      $deleteModal.classList.add("hidden"),
    );

    const confirmBtn = $deleteModal.querySelector("#modal-delete-confirm");
    confirmBtn?.addEventListener("click", async () => {
      const pk = $deleteModal.dataset.modId;
      // Hide the modal right away
      $deleteModal.classList.add("hidden");
      if (!pk) {
        showToast("No module selected for deletion.", "error");
        return;
      }
      await performDelete(pk);
    });
  }

  // -----------------------------------------------------------------
  // Kick‑off – load the first page
  // -----------------------------------------------------------------
  load();
}
