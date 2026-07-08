// -----------------------------------------------------------------
// subject_ajax.js – Ajax widget for “Subjects”
// -----------------------------------------------------------------
import { csrftoken } from "./utils.js";

/**
 * Initialise the subjects widget.
 *
 * Expected data‑attributes on the root element:
 *
 *   data-list-url           → "/slm/api/subjects/"
 *   data-create-url         → "/slm/api/subjects/create/"
 *   data-update-url        → "/slm/api/subjects/0/"          (dummy 0)
 *   data-delete-url        → "/slm/api/subjects/0/delete/"   (dummy 0)
 *
 * The edit UI is a modal (same pattern as in module_ajax.js).
 */
export function initSubjectWidget(rootEl) {
  // -----------------------------------------------------------------
  // 1️⃣  URLs coming from the template (contain a dummy “0”)
  // -----------------------------------------------------------------
  const listUrl   = rootEl.dataset.listUrl;   // …?page=
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl; // “…/subjects/0/”
  const deleteTpl = rootEl.dataset.deleteUrl; // “…/subjects/0/delete/”

  // -----------------------------------------------------------------
  // Helper – replace the dummy “0” with a real id
  // -----------------------------------------------------------------
  // RegExp finds the first 0 that is either the end of the string
  // or followed by a slash – exactly what the module widget does.
  const replaceId = (template, id) => template.replace(/0(?=\/|$)/, id);

  // -----------------------------------------------------------------
  // 2️⃣  DOM shortcuts (all inside the widget)
  // -----------------------------------------------------------------
  const $list   = rootEl.querySelector("#subject-list");
  const $status = rootEl.querySelector("#status");

  const $codeInput   = rootEl.querySelector("#code-input");
  const $nameInput   = rootEl.querySelector("#name-input");
  const $yearSelect  = rootEl.querySelector("#year-select");
  const $addBtn      = rootEl.querySelector("#add-btn");

  // Modal placeholder – the widget will inject the modal the first time
  const $modal = rootEl.querySelector("#subject-edit-modal");

  // -----------------------------------------------------------------
  // 3️⃣  Load the YEAR <select> (same as before)
  // -----------------------------------------------------------------
  async function loadYearChoices() {
    try {
      const resp = await fetch("/slm/api/subjects/year-choices/", {
        credentials: "same-origin",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json(); // {choices: [{value, label}, …]}

      $yearSelect.innerHTML = "";
      data.choices.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.value;
        opt.textContent = c.label;
        $yearSelect.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load year choices:", e);
    }
  }

  // -----------------------------------------------------------------
  // 4️⃣  Render a **single** subject card (clickable, with actions)
  // -----------------------------------------------------------------
  function renderCard(subject) {
    const card = document.createElement("div");
    card.className = "subject-card";
    card.dataset.id = subject.id;

    const link = document.createElement("a");
    link.href = subject.detail_url;
    link.className = "subject-card-link";
    link.setAttribute("aria-label", `Open ${subject.subject_code}`);

    const h1 = document.createElement("h1");
    h1.textContent = subject.subject_code;
    link.appendChild(h1);

    const p = document.createElement("p");
    p.textContent = subject.subject_name;
    link.appendChild(p);

    const year = document.createElement("p");
    year.textContent = `Year: ${subject.year_display}`;
    link.appendChild(year);

    const author = document.createElement("i");
    author.textContent = `By ${subject.author_name}`;
    link.appendChild(author);

    card.appendChild(link);

    // -------------------------------------------------------------
    // Owner‑only actions (edit / delete)
    // -------------------------------------------------------------
    if (subject.is_owner) {
      const actions = document.createElement("div");
      actions.className = "subject-card__actions";

      // ----- Edit -------------------------------------------------
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.title = "Edit";
      editBtn.className = "subject-card__action";
      editBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      editBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openEditModal(subject);               // ← modal version
      });
      actions.appendChild(editBtn);

      // ----- Delete -----------------------------------------------
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.title = "Delete";
      delBtn.className = "subject-card__action subject-card__action--delete";
      delBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
      delBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        deleteSubject(subject.id);
      });
      actions.appendChild(delBtn);

      card.appendChild(actions);
    }

    return card;
  }

  // -----------------------------------------------------------------
  // 5️⃣  Paginator UI (exact copy of the module widget’s paginator)
  // -----------------------------------------------------------------
  function renderPaginator(meta) {
    const old = rootEl.querySelector(".paginator");
    if (old) old.remove();

    const nav = document.createElement("nav");
    nav.className = "paginator";
    nav.setAttribute("aria-label", "Subjects pagination");

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

  // -----------------------------------------------------------------
  // 6️⃣  LOAD – GET a page and render the list
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
      if (data.length === 0) {
        $list.innerHTML = "<p>No subjects yet.</p>";
      } else {
        let row;
        data.forEach((subject, idx) => {
          if (idx % 3 === 0) {
            row = document.createElement("div");
            row.className = "subject-row";
            $list.appendChild(row);
          }
          row.appendChild(renderCard(subject));
        });
      }

      // ---- paginator ----------------------------------------------------
      renderPaginator(payload);
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // 7️⃣  CREATE – POST a new subject (unchanged)
  // -----------------------------------------------------------------
  async function create() {
    if (!$codeInput || !$nameInput) return;

    const payload = {
      subject_code: $codeInput.value.trim(),
      subject_name: $nameInput.value.trim(),
      year: $yearSelect.value,
    };
    if (!payload.subject_code || !payload.subject_name) {
      alert("Both fields are required");
      return;
    }

    try {
      const resp = await fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify(payload),
      });

      if (resp.status === 201) {
        const created = await resp.json();
        $status.textContent = `✅ Created #${created.id}`;
        $codeInput.value = "";
        $nameInput.value = "";
        load(); // stay on page 1
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // 8️⃣  EDIT – modal (mirrors the module widget)
  // -----------------------------------------------------------------
  function openEditModal(subject) {
    // -------------------------------------------------
    // Build the modal **fresh** each time it is opened
    // -------------------------------------------------
    $modal.innerHTML = `
        <div class="modal__backdrop"></div>
        <div class="modal__content">
            <h2>Edit subject</h2>
            <form id="subject-edit-form">
                <input type="hidden" name="subject_id" value="${subject.id}">
                <label>
                    Subject code
                    <input type="text" name="subject_code" value="${subject.subject_code}" required>
                </label>
                <label>
                    Subject name
                    <input type="text" name="subject_name" value="${subject.subject_name}" required>
                </label>
                <label>
                    Year
                    <select name="year">
                        ${[...$yearSelect.options]
                          .map(
                            (opt) =>
                              `<option value="${opt.value}" ${
                                opt.value === subject.year ? "selected" : ""
                              }>${opt.textContent}</option>`
                          )
                          .join("")}
                    </select>
                </label>

                <div class="modal__actions">
                    <button type="submit" class="button-primary">Save</button>
                    <button type="button" class="button-plain" id="subject-cancel">Cancel</button>
                </div>
            </form>
        </div>
    `;

    // ----- cancel button -------------------------------------------------
    $modal.querySelector("#subject-cancel").addEventListener("click", () => {
      $modal.classList.add("hidden");
    });

    // ----- submit handler ------------------------------------------------
    $modal.querySelector("#subject-edit-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.target;
      const sid  = form.subject_id.value;

      const payload = {
        subject_code: form.subject_code.value.trim(),
        subject_name: form.subject_name.value.trim(),
        year: form.year.value,
      };

      const url = replaceId(updateTpl, sid); // <-- correct URL
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

        if (!resp.ok) {
          const err = await resp.json();
          $status.textContent = `❌ ${err.error || resp.statusText}`;
          return;
        }

        $status.textContent = "✅ Subject updated";
        $modal.classList.add("hidden");
        load(); // refresh list
      } catch (err) {
        $status.textContent = `❌ ${err}`;
      }
    });

    // show modal
    $modal.classList.remove("hidden");
  }

  // -----------------------------------------------------------------
  // 9️⃣  DELETE – DELETE a subject (uses replaceId helper)
  // -----------------------------------------------------------------
  async function deleteSubject(pk) {
    if (!confirm("Delete this subject?")) return;
    const url = replaceId(deleteTpl, pk);
    try {
      const resp = await fetch(url, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrftoken },
      });

      if (resp.status === 204) {
        $status.textContent = "✅ Deleted";
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
  // 10️⃣  UI bindings & minimal modal CSS (exactly as in module_ajax.js)
  // -----------------------------------------------------------------
  if ($addBtn) $addBtn.addEventListener("click", create);

  // inject tiny CSS for the modal (you can move it to a static file)
  const style = document.createElement("style");
  style.textContent = `
    #subject-edit-modal.hidden { display: none; }
    #subject-edit-modal {
      position: fixed; inset: 0; z-index: 1000;
      display: flex; align-items: center; justify-content: center;
    }
    #subject-edit-modal .modal__backdrop {
      position: absolute; inset: 0; background: rgba(0,0,0,0.5);
    }
    #subject-edit-modal .modal__content {
      position: relative; background:#fff; padding:1.5rem;
      border-radius:8px; max-width:460px; width:90%;
      box-shadow:0 4px 12px rgba(0,0,0,0.15);
    }
    #subject-edit-modal label { display:block; margin-bottom:.75rem; }
    #subject-edit-modal input[type="text"],
    #subject-edit-modal select {
      width:100%; padding:.4rem .6rem; margin-top:.2rem;
    }
    .modal__actions { text-align:right; margin-top:1rem; }
    .button-primary { background:#2563eb; color:#fff; border:none; padding:.5rem 1rem; border-radius:4px; cursor:pointer; }
    .button-plain   { background:transparent; color:#555; border:none; margin-left:.5rem; cursor:pointer; }
  `;
  document.head.appendChild(style);

  // -----------------------------------------------------------------
  // 11️⃣  Initial load
  // -----------------------------------------------------------------
  loadYearChoices();   // fills the year <select>
  load();              // first page
}
