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

  /* -----------------------------------------------------------------
   * 2️⃣  Toast helper -------------------------------------------------
   * ----------------------------------------------------------------- */
  const getToastContainer = () => {
    let container = rootEl.querySelector(".toast-container");
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container";
      container.setAttribute("aria-live", "polite");
      rootEl.appendChild(container);
    }
    return container;
  };
  const $toastContainer = getToastContainer();

  const showToast = (message, type = "info", duration = 4000) => {
    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.style.setProperty("--toast-life", `${duration}ms`);

    const icon = document.createElement("span");
    icon.className = "toast__icon";
    // (you can add emojis / SVGs here if you like)

    const msg = document.createElement("span");
    msg.textContent = message;

    toast.appendChild(icon);
    toast.appendChild(msg);
    toast.addEventListener("click", () => toast.remove());

    $toastContainer.appendChild(toast);
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

  /* -----------------------------------------------------------------
   * Helper – icons based on file extension
   * ----------------------------------------------------------------- */
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
    const card = document.createElement("div");
    card.className = "pm-card";
    card.dataset.id = mod.id;

    const header = document.createElement("div");
    header.className = "pm-card__header";

    const iconWrap = document.createElement("div");
    iconWrap.className = `pm-card__icon ${getModuleIconClass(mod.file_url)}`.trim();
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
    const ext = fileName.includes(".") ? fileName.split(".").pop().toUpperCase() : "FILE";
    typePill.textContent = ext;
    meta.appendChild(typePill);

    content.appendChild(meta);
    header.appendChild(content);
    card.appendChild(header);

    // ---- Actions -------------------------------------------------
    const actions = document.createElement("div");
    actions.className = "pm-card__actions";

    // View button – links to the module‑detail page
    const viewBtn = document.createElement("a");
    viewBtn.href = `/slm/subjects/${mod.subject_id}/modules/${mod.id}/`;
    viewBtn.className = "button button-plain";
    viewBtn.textContent = "View";
    viewBtn.title = "Open module preview";
    actions.appendChild(viewBtn);

    // Owner‑only edit / delete – use global modal
    if (mod.is_owner) {
      // ---- Edit (global modal) ---------------------------------
      const editLink = document.createElement("a");
      editLink.href = "#";
      editLink.title = "Edit";
      editLink.className = "pm-card__action js-modal-trigger";
      editLink.dataset.url = `/slm/api/modules/${mod.id}/edit-modal/`;
      editLink.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      actions.appendChild(editLink);

      // ---- Delete (global modal) -------------------------------
      const delLink = document.createElement("a");
      delLink.href = "#";
      delLink.title = "Delete";
      delLink.className = "pm-card__action pm-card__action--delete js-modal-trigger";
      delLink.dataset.url = `/slm/api/modules/${mod.id}/delete-modal/`;
      delLink.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
      actions.appendChild(delLink);
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
      makeItem("←", meta.previous_page_number, !meta.has_previous)
    );
    ul.appendChild(makeItem("1", null, false, meta.page === 1));
    if (meta.page - 2 > 2) ul.appendChild(makeItem("…", null, false, false, true));

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
          meta.page === meta.total_pages
        )
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
          "error"
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
   * 8️⃣  UI bindings & modal handling
   * ----------------------------------------------------------------- */
  if ($addBtn) $addBtn.addEventListener("click", create);

  // No longer need local edit / delete modals – the global modal handles them.

  /* -----------------------------------------------------------------
   * 9️⃣ Kick‑off – load the first page
   * ----------------------------------------------------------------- */
  load();
}
