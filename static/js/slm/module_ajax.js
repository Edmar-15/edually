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
  const listUrl        = rootEl.dataset.listUrl;      // …?page=
  const createUrl      = rootEl.dataset.createUrl;
  const updateTpl      = rootEl.dataset.updateUrl;     // “…/modules/0/”
  const deleteTpl      = rootEl.dataset.deleteUrl;     // “…/modules/0/delete/”
  const replaceFileTpl = rootEl.dataset.fileReplaceUrl; // “…/modules/0/file/”

  /* -----------------------------------------------------------------
   * Helper – replace the dummy “0” with a real id
   * ----------------------------------------------------------------- */
  const replaceId = (template, id) => template.replace(/0(?=\/|$)/, id);
  // The RegExp looks for a `0` that is either at the very end of the string
  // or just before a slash – this prevents accidental replacement of a
  // `0` that could appear in a query‑string or elsewhere.

  /* -----------------------------------------------------------------
   * 2️⃣  DOM shortcuts (all inside the widget)
   * ----------------------------------------------------------------- */
  const $list   = rootEl.querySelector("#module-list");
  const $status = rootEl.querySelector("#module-status");

  if (!$list) {
    console.warn("Module widget is missing #module-list container.");
    return;
  }

  const $numInput   = rootEl.querySelector("#module-number-input");
  const $nameInput  = rootEl.querySelector("#module-name-input");
  const $fileInput  = rootEl.querySelector("#module-file-input");
  const $addBtn     = rootEl.querySelector("#module-add-btn");
  const $modal      = rootEl.querySelector("#module-edit-modal");

  function getModuleIconMarkup(fileUrl = "") {
    const ext = (fileUrl || "").split("?")[0].split("#")[0].split(".").pop()?.toLowerCase();

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
    const ext = (fileUrl || "").split("?")[0].split("#")[0].split(".").pop()?.toLowerCase();

    switch (ext) {
      case "pdf":
        return "module-card__preview--pdf";
      case "doc":
      case "docx":
        return "module-card__preview--doc";
      case "ppt":
      case "pptx":
        return "module-card__preview--ppt";
      default:
        return "";
    }
  }

  /* -----------------------------------------------------------------
   * 3️⃣  Render a single module card
   * ----------------------------------------------------------------- */
  function renderCard(mod) {
    const card = document.createElement("div");
    card.className = "module-card";
    card.dataset.id = mod.id;

    const preview = document.createElement("div");
    preview.className = `module-card__preview ${getModuleIconClass(mod.file_url)}`.trim();
    preview.innerHTML = getModuleIconMarkup(mod.file_url);
    card.appendChild(preview);

    const body = document.createElement("div");
    body.className = "module-card__body";

    const link = document.createElement("a");
    link.href = `/slm/subjects/${mod.subject_id}/modules/${mod.id}/` || "#";
    link.className = "module-card__link";
    link.setAttribute("aria-label", `Open ${mod.module_name}`);

    const h2 = document.createElement("h2");
    h2.textContent = `#${mod.module_number} – ${mod.module_name}`;
    link.appendChild(h2);

    const meta = document.createElement("div");
    meta.className = "module-card__meta";

    const typePill = document.createElement("span");
    typePill.className = "module-card__pill";
    const fileName = mod.file_url ? mod.file_url.split("/").pop() : "Document";
    const ext = fileName.includes(".") ? fileName.split(".").pop().toUpperCase() : "FILE";
    typePill.textContent = ext;
    meta.appendChild(typePill);

    if (mod.file_url) {
      const dl = document.createElement("span");
      dl.className = "module-card__pill";
      dl.textContent = "Open";
      meta.appendChild(dl);
    }

    link.appendChild(meta);
    body.appendChild(link);
    card.appendChild(body);

    /* ---- Owner‑only actions --------------------------------------- */
    if (mod.is_owner) {
      const actions = document.createElement("div");
      actions.className = "module-card__actions";

      // ✏️ Edit
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.title = "Edit";
      editBtn.className = "module-card__action";
      editBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      editBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openEditModal(mod);
      });
      actions.appendChild(editBtn);

      // 🗑️ Delete
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.title = "Delete";
      delBtn.className = "module-card__action module-card__action--delete";
      delBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
      delBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        deleteModule(mod.id);
      });
      actions.appendChild(delBtn);

      body.appendChild(actions);
    }

    return card;
  }

  /* -----------------------------------------------------------------
   * 4️⃣  Paginator – unchanged copy‑paste from subject widget
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

    const makeItem = (label, targetPage = null, disabled = false, current = false, ellipsis = false) => {
      const li = document.createElement("li");
      li.className = "paginator__item";
      if (disabled) li.classList.add("paginator__item--disabled");
      if (current)   li.classList.add("paginator__item--current");
      if (ellipsis)  li.classList.add("paginator__item--ellipsis");

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

    ul.appendChild(makeItem("←", meta.previous_page_number, !meta.has_previous));
    ul.appendChild(makeItem("1", null, false, meta.page === 1));
    if (meta.page - 2 > 2) ul.appendChild(makeItem("…", null, false, false, true));

    const start = Math.max(2, meta.page - 1);
    const end   = Math.min(meta.total_pages - 1, meta.page + 1);
    for (let i = start; i <= end; i++) {
      if (i !== 1 && i !== meta.total_pages) {
        ul.appendChild(makeItem(String(i), null, false, meta.page === i));
      }
    }

    if (meta.page + 2 < meta.total_pages - 1) ul.appendChild(makeItem("…", null, false, false, true));
    if (meta.total_pages > 1) {
      ul.appendChild(makeItem(String(meta.total_pages), null, false, meta.page === meta.total_pages));
    }
    ul.appendChild(makeItem("→", meta.next_page_number, !meta.has_next));

    $list.parentNode.appendChild(nav);
  }

  /* -----------------------------------------------------------------
   * 5️⃣  LOAD – fetch a page and render
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
              <div class="module-empty-state__icon">📚</div>
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
      $status.textContent = `❌ ${e}`;
    }
  }

  /* -----------------------------------------------------------------
   * 6️⃣  CREATE – POST a new module (multipart/form‑data)
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
      if (!ALLOWED_EXT.some(ext => name.endsWith(ext))) {
        $status.textContent =
          "❌ Only PDF, Word (.doc/.docx) and PowerPoint (.ppt/.pptx) files are allowed.";
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
        $status.textContent = "✅ Module created";
        $numInput.value = "";
        $nameInput.value = "";
        $fileInput.value = "";
        load();
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  /* -----------------------------------------------------------------
   * 7️⃣  EDIT – open modal form (no more `prompt()`)
   * ----------------------------------------------------------------- */
  function openEditModal(mod) {
    // Build the modal only once – reuse it on subsequent edits
    if ($modal.dataset.built !== "true") {
      $modal.innerHTML = `
        <div class="modal__backdrop"></div>
        <div class="modal__content">
          <h2>Edit module</h2>
          <form id="modal-edit-form">
            <label>
              Module number
              <input type="number" name="module_number" min="1" required>
            </label>
            <label>
              Module name
              <input type="text" name="module_name" required>
            </label>
            <label>
              Replace file (optional)
              <input type="file" name="file" accept=".pdf,.doc,.docx,.ppt,.pptx">
            </label>
            <div class="modal__actions">
              <button type="submit" class="button-primary">Save</button>
              <button type="button" class="button-plain" id="modal-cancel">Cancel</button>
            </div>
          </form>
        </div>`;
      $modal.dataset.built = "true";

      // Cancel button
      $modal.querySelector("#modal-cancel").addEventListener("click", () => {
        $modal.classList.add("hidden");
      });

      // Submit handler
      $modal.querySelector("#modal-edit-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = e.target;
        const number = form.module_number.value.trim();
        const name   = form.module_name.value.trim();
        const file   = form.file.files[0];

        const payload = {};
        if (number) payload.module_number = number;
        if (name)   payload.module_name   = name;

        const updateUrl = replaceId(updateTpl, mod.id);
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
            $status.textContent = `❌ ${err.error || resp.statusText}`;
            return;
          }

          // If the user selected a new file, send it via the dedicated endpoint
          if (file) {
            const replaceUrl = replaceId(replaceFileTpl, mod.id);
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
              $status.textContent = `❌ File replace failed – ${ferr.error || fileResp.statusText}`;
              return;
            }
          }

          $status.textContent = "✅ Module updated";
          $modal.classList.add("hidden");
          load();   // refresh the list
        } catch (err) {
          $status.textContent = `❌ ${err}`;
        }
      });
    }

    // Pre‑fill fields with the current values
    const form = $modal.querySelector("#modal-edit-form");
    form.module_number.value = mod.module_number;
    form.module_name.value   = mod.module_name;
    form.file.value = "";
    $modal.classList.remove("hidden");
  }

  /* -----------------------------------------------------------------
   * 8️⃣  DELETE – DELETE a module (still uses the replaceId helper)
   * ----------------------------------------------------------------- */
  async function deleteModule(pk) {
    if (!confirm("Delete this module?")) return;
    const url = replaceId(deleteTpl, pk);
    try {
      const resp = await fetch(url, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrftoken },
      });
      if (resp.status === 204) {
        $status.textContent = "✅ Deleted";
        load();
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  /* -----------------------------------------------------------------
   * 9️⃣  UI bindings & minimal modal CSS (injected once)
   * ----------------------------------------------------------------- */
  if ($addBtn) $addBtn.addEventListener("click", create);

  const style = document.createElement("style");
  style.textContent = `
    #module-edit-modal.hidden { display: none; }
    #module-edit-modal {
      position: fixed; inset: 0; z-index: 1000;
      display: flex; align-items: center; justify-content: center;
    }
    #module-edit-modal .modal__backdrop {
      position: absolute; inset: 0; background: rgba(0,0,0,0.5);
    }
    #module-edit-modal .modal__content {
      position: relative; background: #fff; padding: 1.5rem;
      border-radius: 8px; max-width: 420px; width: 90%;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    #module-edit-modal label { display: block; margin-bottom: .75rem; }
    #module-edit-modal input[type="text"],
    #module-edit-modal input[type="number"],
    #module-edit-modal input[type="file"] {
      width: 100%; padding: .4rem .6rem; margin-top: .2rem;
    }
    .modal__actions { text-align: right; margin-top: 1rem; }
    .button-primary { background: #2563eb; color:#fff; border:none; padding:.5rem 1rem; border-radius:4px; cursor:pointer;}
    .button-plain   { background: transparent; color:#555; border:none; margin-left:.5rem; cursor:pointer;}
  `;
  document.head.appendChild(style);

  /* -----------------------------------------------------------------
   * 10️⃣  Initial load
   * ----------------------------------------------------------------- */
  load();   // first page
}
