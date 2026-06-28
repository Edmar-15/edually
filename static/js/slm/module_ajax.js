// ---------------------------------------------------------------
// moduleWidget.js – Ajax widget for “Modules” of a Subject
// ---------------------------------------------------------------
import { csrftoken } from "./utils.js";

/**
 * Initialise the modules widget.
 *
 * Expected data‑attributes on the root element:
 *
 *   data-list-url   → "/slm/api/subjects/42/modules/"
 *   data-create-url → "/slm/api/subjects/42/modules/create/"
 *   data-update-url → "/slm/api/modules/{id}/"
 *   data-delete-url → "/slm/api/modules/{id}/delete/"
 */
export function initModuleWidget(rootEl) {
  // -----------------------------------------------------------------
  // 1️⃣  URLs from data‑attributes
  // -----------------------------------------------------------------
  const listUrl   = rootEl.dataset.listUrl;   // …?page=
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl; // “…/modules/{id}/”
  const deleteTpl = rootEl.dataset.deleteUrl; // “…/modules/{id}/delete/”

  // -----------------------------------------------------------------
  // 2️⃣  DOM shortcuts (all inside the widget)
  // -----------------------------------------------------------------
  const $list   = rootEl.querySelector("#module-list");
  const $status = rootEl.querySelector("#module-status");

  // Create‑form (only for owners – you can hide it with an {% if %} in the template)
  const $numInput   = rootEl.querySelector("#module-number-input");
  const $nameInput  = rootEl.querySelector("#module-name-input");
  const $fileInput  = rootEl.querySelector("#module-file-input");
  const $addBtn     = rootEl.querySelector("#module-add-btn");

  // -----------------------------------------------------------------
  // 3️⃣  Render a single module card
  // -----------------------------------------------------------------
  function renderCard(mod) {
    const card = document.createElement("div");
    card.className = "module-card";
    card.dataset.id = mod.id;

    const preview = document.createElement("div");
    preview.className = "module-card__preview";
    card.appendChild(preview);

    const body = document.createElement("div");
    body.className = "module-card__body";

    // Whole card is a link to the file (if present)
    const link = document.createElement("a");
    link.href = mod.file_url || "#";
    link.className = "module-card__link";
    link.setAttribute("aria-label", `Open ${mod.module_name}`);
    link.target = "_blank";

    const h2 = document.createElement("h2");
    h2.textContent = `#${mod.module_number} – ${mod.module_name}`;
    link.appendChild(h2);

    const meta = document.createElement("div");
    meta.className = "module-card__meta";

    const typePill = document.createElement("span");
    typePill.className = "module-card__pill";
    const fileName = mod.file_url ? mod.file_url.split("/").pop() : "Document";
    const extension = fileName.includes(".") ? fileName.split(".").pop().toUpperCase() : "FILE";
    typePill.textContent = extension;
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

    // Owner‑only actions ------------------------------------------------
    if (mod.is_owner) {
      const actions = document.createElement("div");
      actions.className = "module-card__actions";

      // ✏️ Edit button
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.title = "Edit";
      editBtn.className = "module-card__action";
      editBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      editBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        editModule(mod);
      });
      actions.appendChild(editBtn);

      // 🗑️ Delete button
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

  // -----------------------------------------------------------------
  // 4️⃣  Paginator – copy‑paste from subjectWidget (no changes)
  // -----------------------------------------------------------------
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
      if (ellipsis)   li.classList.add("paginator__item--ellipsis");

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

    // ← prev
    ul.appendChild(makeItem("←", meta.previous_page_number, !meta.has_previous));

    // first page
    ul.appendChild(makeItem("1", null, false, meta.page === 1));

    // gap before inner window
    if (meta.page - 2 > 2) ul.appendChild(makeItem("…", null, false, false, true));

    // inner pages (max 5)
    const start = Math.max(2, meta.page - 1);
    const end   = Math.min(meta.total_pages - 1, meta.page + 1);
    for (let i = start; i <= end; i++) {
      if (i !== 1 && i !== meta.total_pages) {
        ul.appendChild(makeItem(String(i), null, false, meta.page === i));
      }
    }

    // gap after inner window
    if (meta.page + 2 < meta.total_pages - 1) ul.appendChild(makeItem("…", null, false, false, true));

    // last page
    if (meta.total_pages > 1) {
      ul.appendChild(makeItem(String(meta.total_pages), null, false, meta.page === meta.total_pages));
    }

    // → next
    ul.appendChild(makeItem("→", meta.next_page_number, !meta.has_next));

    $list.parentNode.appendChild(nav);
  }

  // -----------------------------------------------------------------
  // 5️⃣  LOAD – fetch a page and render
  // -----------------------------------------------------------------
  async function load(page = 1) {
    try {
      const resp = await fetch(`${listUrl}?page=${page}`, {
        credentials: "same-origin",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const payload = await resp.json();

      // ---- render cards -------------------------------------------------
      $list.innerHTML = "";
      const data = payload.results;
      if (!data.length) {
        $list.innerHTML = "<p>No modules yet.</p>";
      } else {
        // we keep the 3‑per‑row layout that the subject widget uses
        let row;
        data.forEach((mod, idx) => {
          if (idx % 3 === 0) {
            row = document.createElement("div");
            row.className = "module-row";
            $list.appendChild(row);
          }
          row.appendChild(renderCard(mod));
        });
      }

      // ---- paginator ----------------------------------------------------
      renderPaginator(payload);
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // 6️⃣  CREATE – POST a new module (multipart/form‑data)
  // -----------------------------------------------------------------
  async function create() {
    if (!$numInput || !$nameInput || !$fileInput) return;

    const form = new FormData();
    form.append("module_number", $numInput.value.trim());
    form.append("module_name", $nameInput.value.trim());
    // -----------------------------------------------------------------
    //  📎  Validate file type before we ever send it to the server
    // -----------------------------------------------------------------
    const file = $fileInput.files[0];
    if (file) {
      const ALLOWED_EXT = [".pdf", ".doc", ".docx", ".ppt", ".pptx"];
      const name = file.name.toLowerCase();
      const hasAllowedExt = ALLOWED_EXT.some((ext) => name.endsWith(ext));
      if (!hasAllowedExt) {
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
        // clear the form
        $numInput.value = "";
        $nameInput.value = "";
        $fileInput.value = "";
        load(); // refresh current page
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // 7️⃣  UPDATE – PUT a module (JSON only – no file change)
  // -----------------------------------------------------------------
  async function editModule(mod) {
    const newNum  = prompt("New number (blank = keep old)", mod.module_number);
    const newName = prompt("New name (blank = keep old)", mod.module_name);

    const payload = {};
    if (newNum !== null && newNum.trim() !== "") payload.module_number = newNum.trim();
    if (newName !== null && newName.trim() !== "") payload.module_name = newName.trim();

    if (!Object.keys(payload).length) return; // nothing changed

    const url = updateTpl.replace("{id}", mod.id);
    try {
      const resp = await fetch(url, {
        method: "PUT",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify(payload),
      });
      if (resp.ok) {
        $status.textContent = "✅ Updated";
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
  // 8️⃣  DELETE – DELETE a module
  // -----------------------------------------------------------------
  async function deleteModule(pk) {
    if (!confirm("Delete this module?")) return;
    const url = deleteTpl.replace("{id}", pk);
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
  // 9️⃣  UI bindings
  // -----------------------------------------------------------------
  if ($addBtn) $addBtn.addEventListener("click", create);
  load(); // first page
}
