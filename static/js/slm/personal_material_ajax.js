// -------------------------------------------------------------------
// personal_material_ajax.js – CRUD widget for PersonalMaterial
// -------------------------------------------------------------------
import { csrftoken } from "./utils.js";

/**
 * Initialise the Personal‑Material widget.
 *
 * Expected data‑attributes on the root element:
 *
 *   data-list-url           → "/slm/api/personal-materials/"
 *   data-create-url         → "/slm/api/personal-materials/create/"
 *   data-update-url         → "/slm/api/personal-materials/0/"
 *   data-delete-url         → "/slm/api/personal-materials/0/delete/"
 *   data-file-replace-url   → "/slm/api/personal-materials/0/file/"
 *
 * Optional: `data-visibility="public"` – forces the list request to
 * return only public items (used by the “Public Learning Materials” tab).
 */
export function initPersonalMaterialWidget(rootEl) {
  // -----------------------------------------------------------------
  // URLs & helper to swap the dummy “0”
  // -----------------------------------------------------------------
  const listUrl = rootEl.dataset.listUrl;
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl;
  const deleteTpl = rootEl.dataset.deleteUrl;
  const replaceFileTpl = rootEl.dataset.fileReplaceUrl;

  const replaceId = (tmpl, id) => tmpl.replace(/0(?=\/|$)/, id);

  // -----------------------------------------------------------------
  // DOM shortcuts
  // -----------------------------------------------------------------
  const $list = rootEl.querySelector("#personal-material-list");
  const $status = rootEl.querySelector("#personal-material-status");

  const $titleInput = rootEl.querySelector("#pm-title-input");
  const $fileInput = rootEl.querySelector("#pm-file-input");
  const $visibilitySelect = rootEl.querySelector("#pm-visibility-select");
  const $addBtn = rootEl.querySelector("#pm-add-btn");
  const $modal = rootEl.querySelector("#pm-edit-modal");

  // -----------------------------------------------------------------
  // Render a single material card
  // -----------------------------------------------------------------
  function renderCard(pm) {
    const card = document.createElement("div");
    card.className = "pm-card";
    card.dataset.id = pm.id;

    const header = document.createElement("div");
    header.className = "pm-card__header";

    const title = document.createElement("h3");
    title.textContent = pm.title;
    header.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "pm-card__meta";

    // visibility pill
    const visPill = document.createElement("span");
    visPill.className = "pm-card__pill";
    visPill.textContent = pm.visibility_display;
    meta.appendChild(visPill);

    // author pill
    const authorPill = document.createElement("span");
    authorPill.className = "pm-card__pill";
    authorPill.textContent = `by ${pm.author_name}`;
    meta.appendChild(authorPill);

    header.appendChild(meta);
    card.appendChild(header);

    // actions – always show “Download” and a “View” button
    const actions = document.createElement("div");
    actions.className = "pm-card__actions";

    // --- View (preview page) ---------------------------------------
    const viewBtn = document.createElement("a");
    viewBtn.href = `/slm/personal-material/${pm.id}/`;   // matches the URL added in urls.py
    viewBtn.className = "button button-plain";
    viewBtn.textContent = "View";
    viewBtn.title = "Open preview page";
    actions.appendChild(viewBtn);

    // owner‑only edit / delete
    if (pm.is_owner) {
      // Edit -------------------------------------------------------
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.title = "Edit";
      editBtn.className = "pm-card__action";
      editBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      editBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openEditModal(pm);
      });
      actions.appendChild(editBtn);

      // Delete -----------------------------------------------------
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.title = "Delete";
      delBtn.className = "pm-card__action pm-card__action--delete";
      delBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
      delBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        deleteMaterial(pm.id);
      });
      actions.appendChild(delBtn);
    }

    card.appendChild(actions);
    return card;
  }

  // -----------------------------------------------------------------
  // Paginator – same logic as the other widgets
  // -----------------------------------------------------------------
  function renderPaginator(meta) {
    const old = rootEl.querySelector(".paginator");
    if (old) old.remove();

    const nav = document.createElement("nav");
    nav.className = "paginator";
    nav.setAttribute("aria-label", "Materials pagination");
    const ul = document.createElement("ul");
    ul.className = "paginator__list";

    const makeItem = (label, targetPage = null, disabled = false, current = false, ellipsis = false) => {
      const li = document.createElement("li");
      li.className = "paginator__item";
      if (disabled) li.classList.add("paginator__item--disabled");
      if (current)   li.classList.add("paginator__item--current");
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

    ul.appendChild(makeItem("←", meta.previous_page_number, !meta.has_previous));
    ul.appendChild(makeItem("1", null, false, meta.page === 1));
    if (meta.page - 2 > 2) ul.appendChild(makeItem("…", null, false, false, true));

    const start = Math.max(2, meta.page - 1);
    const end = Math.min(meta.total_pages - 1, meta.page + 1);
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

  // -----------------------------------------------------------------
  // LOAD – GET a page and render the list
  // -----------------------------------------------------------------
  async function load(page = 1) {
    try {
      const extra = rootEl.dataset.visibility ? `&visibility=${rootEl.dataset.visibility}` : "";
      const resp = await fetch(`${listUrl}?page=${page}${extra}`, {
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
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // CREATE – POST multipart
  // -----------------------------------------------------------------
  async function create() {
    if (!$titleInput || !$fileInput) return;

    const form = new FormData();
    form.append("title", $titleInput.value.trim());
    form.append("visibility", $visibilitySelect ? $visibilitySelect.value : "PR");
    const file = $fileInput.files[0];
    if (!file) {
      $status.textContent = "❌ Choose a file to upload.";
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
        $status.textContent = "✅ Material created";
        $titleInput.value = "";
        $fileInput.value = "";
        if ($visibilitySelect) $visibilitySelect.value = "PR";
        load();
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // EDIT – open modal (metadata + optional file replace)
  // -----------------------------------------------------------------
  function openEditModal(pm) {
    // Build the modal only once
    if ($modal.dataset.built !== "true") {
      $modal.innerHTML = `
        <div class="modal__backdrop"></div>
        <div class="modal__content">
          <h2>Edit material</h2>
          <form id="pm-edit-form">
            <label>
              Title
              <input type="text" name="title" required>
            </label>
            <label>
              Visibility
              <select name="visibility">
                <option value="PR">Private</option>
                <option value="PU">Public</option>
              </select>
            </label>
            <label>
              Replace file (optional)
              <input type="file" name="file" accept=".pdf,.doc,.docx,.ppt,.pptx">
            </label>
            <div class="modal__actions">
              <button type="submit" class="button-primary">Save</button>
              <button type="button" class="button-plain" id="pm-cancel">Cancel</button>
            </div>
          </form>
        </div>`;
      $modal.dataset.built = "true";

      $modal.querySelector("#pm-cancel").addEventListener("click", () => {
        $modal.classList.add("hidden");
      });

      $modal.querySelector("#pm-edit-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = e.target;
        const title = form.title.value.trim();
        const visibility = form.visibility.value;
        const file = form.file.files[0];

        const payload = { title, visibility };

        const updateUrl = replaceId(updateTpl, pm.id);
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

          // If a new file was selected – upload it via the dedicated endpoint
          if (file) {
            const replaceUrl = replaceId(replaceFileTpl, pm.id);
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

          $status.textContent = "✅ Material updated";
          $modal.classList.add("hidden");
          load();
        } catch (err) {
          $status.textContent = `❌ ${err}`;
        }
      });
    }

    // Populate fields
    const form = $modal.querySelector("#pm-edit-form");
    form.title.value = pm.title;
    form.visibility.value = pm.visibility;
    form.file.value = "";
    $modal.classList.remove("hidden");
  }

  // -----------------------------------------------------------------
  // DELETE – DELETE request
  // -----------------------------------------------------------------
  async function deleteMaterial(pk) {
    if (!confirm("Delete this material?")) return;
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

  // -----------------------------------------------------------------
  // UI bindings & minimal modal CSS (inject once)
  // -----------------------------------------------------------------
  if ($addBtn) $addBtn.addEventListener("click", create);

  const style = document.createElement("style");
  style.textContent = `
    #pm-edit-modal.hidden { display:none; }
    #pm-edit-modal {
      position:fixed; inset:0; z-index:1000;
      display:flex; align-items:center; justify-content:center;
    }
    #pm-edit-modal .modal__backdrop { position:absolute; inset:0; background:rgba(0,0,0,0.5); }
    #pm-edit-modal .modal__content {
      position:relative; background:#fff; padding:1.5rem;
      border-radius:8px; max-width:420px; width:90%;
      box-shadow:0 4px 12px rgba(0,0,0,0.15);
    }
    #pm-edit-modal label { display:block; margin-bottom:.75rem; }
    #pm-edit-modal input[type=text],
    #pm-edit-modal input[type=file],
    #pm-edit-modal select {
      width:100%; padding:.4rem .6rem; margin-top:.2rem;
    }
    .modal__actions { text-align:right; margin-top:1rem; }
    .button-primary { background:#2563eb; color:#fff; border:none; padding:.5rem 1rem; border-radius:4px; cursor:pointer; }
    .button-plain   { background:transparent; color:#555; border:none; margin-left:.5rem; cursor:pointer; }
  `;
  document.head.appendChild(style);

  // -----------------------------------------------------------------
  // Initial load
  // -----------------------------------------------------------------
  load();
}
