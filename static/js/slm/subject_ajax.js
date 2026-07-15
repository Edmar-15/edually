// ---------------------------------------------------------------
// subject_ajax.js – Ajax widget for “Subjects” (toast notifications)
// ---------------------------------------------------------------
import { csrftoken } from "./utils.js";

/**
 * Initialise the subjects widget.
 *
 * Expected data‑attributes on the root element:
 *
 *   data-list-url   → "/slm/api/subjects/"
 *   data-create-url → "/slm/api/subjects/create/"
 *   data-update-url → "/slm/api/subjects/0/"   (dummy 0)
 *   data-delete-url → "/slm/api/subjects/0/delete/"
 *
 * The edit UI lives in a static modal that is already present in the
 * template (see `tab_self.html`).  A delete‑confirmation modal is also
 * static.
 */
export function initSubjectWidget(rootEl) {
  /* -----------------------------------------------------------------
   * 1️⃣  URLs – they come from data‑attributes on the root element.
   * ----------------------------------------------------------------- */
  const listUrl   = rootEl.dataset.listUrl;
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl; // “…/subjects/0/”
  const deleteTpl = rootEl.dataset.deleteUrl; // “…/subjects/0/delete/”

  /* -----------------------------------------------------------------
   * 2️⃣  Helper – replace the dummy “0” with a real id.
   * ----------------------------------------------------------------- */
  const replaceId = (template, id) => template.replace(/0(?=\/|$)/, id);

  /* -----------------------------------------------------------------
   * 3️⃣  Toast helper – identical to the one used in module_ajax.js.
   * ----------------------------------------------------------------- */
  const getToastContainer = () => {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container";
      container.setAttribute("aria-live", "polite");
      document.body.appendChild(container);
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
    toast.appendChild(icon);

    const msg = document.createElement("span");
    msg.textContent = message;
    toast.appendChild(msg);

    toast.addEventListener("click", () => toast.remove());
    $toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), duration + 500);
  };

  /* -----------------------------------------------------------------
   * 4️⃣  DOM shortcuts (all inside the widget)
   * ----------------------------------------------------------------- */
  const $list       = rootEl.querySelector("#subject-list");
  const $codeInput  = rootEl.querySelector("#code-input");
  const $nameInput  = rootEl.querySelector("#name-input");
  const $yearSelect = rootEl.querySelector("#year-select");
  const $addBtn     = rootEl.querySelector("#add-btn");
  const $editModal  = rootEl.querySelector("#subject-edit-modal");
  const $deleteModal = rootEl.querySelector("#subject-delete-modal");

  /* -----------------------------------------------------------------
   * 5️⃣  Load the YEAR <select> with choices from the API.
   * ----------------------------------------------------------------- */
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
      showToast(`Failed to load year choices – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 6️⃣  Render a single subject card (incl. edit / delete actions).
   * ----------------------------------------------------------------- */
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

    const pName = document.createElement("p");
    pName.textContent = subject.subject_name;
    link.appendChild(pName);

    const pYear = document.createElement("p");
    pYear.textContent = `Year: ${subject.year_display}`;
    link.appendChild(pYear);

    const pAuthor = document.createElement("i");
    pAuthor.textContent = `By ${subject.author_name}`;
    link.appendChild(pAuthor);

    card.appendChild(link);

    // Owner‑only actions
    if (subject.is_owner) {
      const actions = document.createElement("div");
      actions.className = "subject-card__actions";

      // Edit button -------------------------------------------------
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.title = "Edit";
      editBtn.className = "subject-card__action";
      editBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
      editBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openEditModal(subject);
      });
      actions.appendChild(editBtn);

      // Delete button ------------------------------------------------
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.title = "Delete";
      delBtn.className = "subject-card__action subject-card__action--delete";
      delBtn.innerHTML =
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
      delBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openDeleteModal(subject.id);
      });
      actions.appendChild(delBtn);

      card.appendChild(actions);
    }

    return card;
  }

  /* -----------------------------------------------------------------
   * 7️⃣  Paginator – same layout as the module widget.
   * ----------------------------------------------------------------- */
  function renderPaginator(meta) {
    const old = rootEl.querySelector(".paginator");
    if (old) old.remove();

    const nav = document.createElement("nav");
    nav.className = "paginator";
    nav.setAttribute("aria-label", "Subjects pagination");

    const ul = document.createElement("ul");
    ul.className = "paginator__list";
    nav.appendChild(ul);

    const makeItem = (label, targetPage = null, disabled = false, current = false, ellipsis = false) => {
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
      ul.appendChild(
        makeItem(String(meta.total_pages), null, false, meta.page === meta.total_pages)
      );
    }
    ul.appendChild(makeItem("→", meta.next_page_number, !meta.has_next));

    $list.parentNode.appendChild(nav);
  }

  /* -----------------------------------------------------------------
   * 8️⃣  LOAD – GET a page and render the list.
   * ----------------------------------------------------------------- */
  async function load(page = 1) {
    try {
      const resp = await fetch(`${listUrl}?page=${page}`, {
        credentials: "same-origin",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const payload = await resp.json();

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

      renderPaginator(payload);
    } catch (e) {
      showToast(`Failed to load subjects – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 9️⃣  CREATE – POST a new subject.
   * ----------------------------------------------------------------- */
  async function create() {
    if (!$codeInput || !$nameInput) return;

    const payload = {
      subject_code: $codeInput.value.trim(),
      subject_name: $nameInput.value.trim(),
      year: $yearSelect.value,
    };

    if (!payload.subject_code || !payload.subject_name) {
      showToast("Both Subject code and Subject name are required.", "error");
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
        showToast(`Subject ${created.subject_name} created`, "success");
        $codeInput.value = "";
        $nameInput.value = "";
        load(); // stay on page 1
      } else {
        const err = await resp.json();
        showToast(err.error || resp.statusText, "error");
      }
    } catch (e) {
      showToast(`Failed to create subject – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 🔟  OPEN EDIT MODAL – fill the static form.
   * ----------------------------------------------------------------- */
  function openEditModal(subject) {
    $editModal.dataset.subjectId = subject.id;

    const form = $editModal.querySelector("#subject-edit-form");

    // hidden field
    form.subject_id.value = subject.id;

    // basic inputs
    form.subject_code.value = subject.subject_code;
    form.subject_name.value = subject.subject_name;

    // year <select> – copy the options from the add‑form
    const yearSel = form.year;
    yearSel.innerHTML = "";
    [...$yearSelect.options].forEach((opt) => {
      const newOpt = document.createElement("option");
      newOpt.value = opt.value;
      newOpt.textContent = opt.textContent;
      if (opt.value === subject.year) newOpt.selected = true;
      yearSel.appendChild(newOpt);
    });

    $editModal.classList.remove("hidden");
  }

  /* -----------------------------------------------------------------
   * 🗑️  OPEN DELETE MODAL
   * ----------------------------------------------------------------- */
  function openDeleteModal(pk) {
    $deleteModal.dataset.subjectId = pk;
    $deleteModal.classList.remove("hidden");
  }

  /* -----------------------------------------------------------------
   * 1️⃣1️⃣  PERFORM DELETE – called from the delete‑confirmation modal.
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
      showToast(`Failed to delete subject – ${e}`, "error");
    }
  }

  /* -----------------------------------------------------------------
   * 1️⃣2️⃣  UI bindings & modal handling
   * ----------------------------------------------------------------- */
  if ($addBtn) $addBtn.addEventListener("click", create);

  // ---- Edit modal -------------------------------------------------
  const editCancel = $editModal.querySelector("#subject-cancel");
  editCancel?.addEventListener("click", () => $editModal.classList.add("hidden"));

  const editForm = $editModal.querySelector("#subject-edit-form");
  editForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const sid = form.subject_id.value;

    const payload = {
      subject_code: form.subject_code.value.trim(),
      subject_name: form.subject_name.value.trim(),
      year: form.year.value,
    };

    const url = replaceId(updateTpl, sid);
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
        showToast(err.error || resp.statusText, "error");
        return;
      }

      showToast("Subject updated", "success");
      $editModal.classList.add("hidden");
      load(); // refresh the list
    } catch (err) {
      showToast(`Failed to update subject – ${err}`, "error");
    }
  });

  // ---- Delete modal ------------------------------------------------
  const deleteCancel = $deleteModal.querySelector("#subject-delete-cancel");
  deleteCancel?.addEventListener("click", () => $deleteModal.classList.add("hidden"));

  const deleteConfirm = $deleteModal.querySelector("#subject-delete-confirm");
  deleteConfirm?.addEventListener("click", async () => {
    const pk = $deleteModal.dataset.subjectId;
    $deleteModal.classList.add("hidden");
    if (!pk) {
      showToast("No subject selected for deletion.", "error");
      return;
    }
    await performDelete(pk);
  });

  // -----------------------------------------------------------------
  // 1️⃣3️⃣  Initial load.
  // -----------------------------------------------------------------
  loadYearChoices(); // populate the year <select> used by both forms
  load();            // fetch the first page of subjects
}