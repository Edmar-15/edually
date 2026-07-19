// -------------------------------------------------------------------
// personal_material_ajax.js – CRUD widget for PersonalMaterial
// -------------------------------------------------------------------
import { csrftoken } from "./utils.js";

/**
 * Initialise the Personal‑Material widget.
 *
 * Expected data‑attributes on the root element:
 *
 *   data-list-url          → "/slm/api/personal-materials/"
 *   data-create-url        → "/slm/api/personal-materials/create/"
 *   data-update-url        → "/slm/api/personal-materials/0/"   (dummy 0)
 *   data-delete-url        → "/slm/api/personal-materials/0/delete/"
 *   data-file-replace-url  → "/slm/api/personal-materials/0/file/"
 *
 * All user‑feedback (success, error, info) is now shown as toast
 * notifications (the same style used for the Modules widget).
 */
export function initPersonalMaterialWidget(rootEl) {
  /* -----------------------------------------------------------------
   * 1️⃣  URLs & helper to replace the dummy “0” with a real id.
   * ----------------------------------------------------------------- */
  const listUrl = rootEl.dataset.listUrl;
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl; // “…/0/”
  const deleteTpl = rootEl.dataset.deleteUrl; // “…/0/delete/”
  const replaceFileTpl = rootEl.dataset.fileReplaceUrl; // “…/0/file/”

  const replaceId = (tmpl, id) => tmpl.replace(/0(?=\/|$)/, id);

  /* -----------------------------------------------------------------
   * 2️⃣  Toast helper – identical to the one used in `module_ajax.js`.
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
    // (add icons / emojis if you wish)

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
  const $list = rootEl.querySelector("#personal-material-list");
  if (!$list) {
    console.warn(
      "Personal‑Material widget is missing #personal-material-list container."
    );
    return;
  }

  const $titleInput = rootEl.querySelector("#pm-title-input");
  const $fileInput = rootEl.querySelector("#pm-file-input");
  const $visibilitySelect = rootEl.querySelector("#pm-visibility-select");
  const $filterVisibility = rootEl.querySelector(
    "#pm-filter-visibility-select"
  );
  const $filterType = rootEl.querySelector("#pm-filter-type-select");
  const $addBtn = rootEl.querySelector("#pm-add-btn");

  /* -----------------------------------------------------------------
   * 4️⃣  Current filter state (used on every load)
   * ----------------------------------------------------------------- */
  const currentFilters = {
    type: $filterType ? $filterType.value : "all",
    visibility:
      rootEl.dataset.visibility ||
      ($filterVisibility ? $filterVisibility.value : "own"),
  };

  /* -----------------------------------------------------------------
   * 5️⃣  Icon helpers (same as Modules widget)
   * ----------------------------------------------------------------- */
  const getMaterialIconMarkup = (fileUrl = "") => {
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
  };
  const getMaterialIconClass = (fileUrl = "") => {
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
  };

  /* -----------------------------------------------------------------
   * 6️⃣  Render a single material card
   * ----------------------------------------------------------------- */
  function renderCard(pm) {
    const card = document.createElement("div");
    card.className = "pm-card";
    card.dataset.id = pm.id;

    const header = document.createElement("div");
    header.className = "pm-card__header";

    const iconWrap = document.createElement("div");
    iconWrap.className = `pm-card__icon ${getMaterialIconClass(pm.file_url)}`.trim();
    iconWrap.innerHTML = getMaterialIconMarkup(pm.file_url);
    header.appendChild(iconWrap);

    const content = document.createElement("div");
    content.className = "pm-card__content";

    const title = document.createElement("h3");
    title.textContent = pm.title;
    content.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "pm-card__meta";

    // visibility pill
    const visPill = document.createElement("span");
    visPill.className = "pm-card__pill pm-card__pill--visibility";
    visPill.innerHTML =
      pm.visibility === "PU"
        ? '<i class="fas fa-globe" aria-hidden="true" title="Public"></i>'
        : '<i class="fas fa-lock" aria-hidden="true" title="Private"></i>';
    meta.appendChild(visPill);

    // author pill
    const authorPill = document.createElement("span");
    authorPill.className = "pm-card__pill";
    authorPill.textContent = `by ${pm.author_name}`;
    meta.appendChild(authorPill);

    content.appendChild(meta);
    header.appendChild(content);
    card.appendChild(header);

    // ---- Actions -------------------------------------------------
    const actions = document.createElement("div");
    actions.className = "pm-card__actions";

    // View (always present)
    const viewBtn = document.createElement("a");
    viewBtn.href = `/slm/personal-material/${pm.id}/`;
    viewBtn.className = "button button-plain";
    viewBtn.textContent = "View";
    viewBtn.title = "Open preview page";
    actions.appendChild(viewBtn);

    // Owner‑only actions – edit / delete via global modal
    if (pm.is_owner) {
      // ---- Edit (global modal) ---------------------------------
      const editLink = document.createElement("a");
      editLink.href = "#";
      editLink.title = "Edit";
      editLink.className = "pm-card__action js-modal-trigger";
      editLink.dataset.url = `/slm/api/personal-materials/${pm.id}/edit-modal/`;
      editLink.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      actions.appendChild(editLink);

      // ---- Delete (global modal) -------------------------------
      const delLink = document.createElement("a");
      delLink.href = "#";
      delLink.title = "Delete";
      delLink.className = "pm-card__action pm-card__action--delete js-modal-trigger";
      delLink.dataset.url = `/slm/api/personal-materials/${pm.id}/delete-modal/`;
      delLink.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
      actions.appendChild(delLink);
    }

    card.appendChild(actions);
    return card;
  }

  /* -----------------------------------------------------------------
   * 7️⃣  Pagination – copy‑paste from the modules widget
   * ----------------------------------------------------------------- */
  function renderPaginator(meta) {
    const old = rootEl.querySelector(".paginator");
    if (old) old.remove();

    const nav = document.createElement("nav");
    nav.className = "paginator";
    nav.setAttribute("aria-label", "Materials pagination");
    const ul = document.createElement("ul");
    ul.className = "paginator__list";

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
   * 8️⃣  LOAD – GET a page and render the list
   * ----------------------------------------------------------------- */
  async function load(page = 1) {
    try {
      const params = new URLSearchParams({ page });

      // visibility can be forced from the template (e.g. owner‑only)
      if (rootEl.dataset.visibility) {
        params.set("visibility", rootEl.dataset.visibility);
      } else {
        params.set("visibility", currentFilters.visibility);
      }
      if (currentFilters.type && currentFilters.type !== "all") {
        params.set("type", currentFilters.type);
      }

      const resp = await fetch(`${listUrl}?${params.toString()}`, {
        credentials: "same-origin",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const payload = await resp.json();

      $list.innerHTML = "";
      if (payload.results.length === 0) {
        $list.innerHTML = "<p>No learning materials yet.</p>";
      } else {
        let row;
        payload.results.forEach((pm, idx) => {
          if (idx % 3 === 0) {
            row = document.createElement("div");
            row.className = "pm-row";
            $list.appendChild(row);
          }
          row.appendChild(renderCard(pm));
        });
      }

      renderPaginator(payload);
    } catch (e) {
      showToast(`Failed to load materials – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 9️⃣  FILTER UI – visibility / type dropdowns
   * ----------------------------------------------------------------- */
  function attachFilters() {
    if ($filterVisibility) {
      $filterVisibility.addEventListener("change", (e) => {
        currentFilters.visibility = e.target.value;
        load(1);
      });
    }
    if ($filterType) {
      $filterType.addEventListener("change", (e) => {
        currentFilters.type = e.target.value;
        load(1);
      });
    }
  }
  if ($filterVisibility || $filterType) attachFilters();

  /* -----------------------------------------------------------------
   * 🔟  CREATE – multipart POST new material
   * ----------------------------------------------------------------- */
  async function create() {
    if (!$titleInput || !$fileInput) return;

    const form = new FormData();
    form.append("title", $titleInput.value.trim());
    form.append(
      "visibility",
      $visibilitySelect ? $visibilitySelect.value : "PR"
    );

    const file = $fileInput.files[0];
    if (!file) {
      showToast("Choose a file before uploading.", "error");
      return;
    }
    form.append("file", file);

    try {
      const resp = await fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrftoken },
        body: form,
      });

      if (resp.status === 201) {
        showToast("Material created", "success");
        $titleInput.value = "";
        $fileInput.value = "";
        if ($visibilitySelect) $visibilitySelect.value = "PR";
        load();
      } else {
        const err = await resp.json();
        showToast(err.error || resp.statusText, "error");
      }
    } catch (e) {
      showToast(`Failed to create material – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 1️⃣1️⃣  UI bindings – Add‑material button
   * ----------------------------------------------------------------- */
  if ($addBtn) $addBtn.addEventListener("click", create);

  /* -----------------------------------------------------------------
   * 1️⃣2️⃣  Kick‑off – load the first page
   * ----------------------------------------------------------------- */
  load();
}