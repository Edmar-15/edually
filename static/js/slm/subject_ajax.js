import { csrftoken } from "./utils.js";

/**
 * Set up the Subjects widget.
 *
 * Expected data‑attributes on the root element:
 *
 *   data-list-url    → "/slm/api/subjects/"
 *   data-create-url  → "/slm/api/subjects/create/"
 *   data-update-url  → "/slm/api/subjects/0/"       (dummy 0)
 *   data-delete-url  → "/slm/api/subjects/0/delete/"
 *
 */
export function initSubjectWidget(rootEl) {
  const listUrl   = rootEl.dataset.listUrl;
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl; // “…/subjects/0/”
  const deleteTpl = rootEl.dataset.deleteUrl; // “…/subjects/0/delete/”

  const replaceId = (template, id) => template.replace(/0(?=\/|$)/, id);

  const showToast = (message, type = "info", duration = 4000) =>
    window.showGlobalToast(message, type, duration);

  const $list        = rootEl.querySelector("#subject-list");
  const $codeInput   = rootEl.querySelector("#code-input");
  const $nameInput   = rootEl.querySelector("#name-input");
  const $yearSelect  = rootEl.querySelector("#year-select");
  const $subjectForm = rootEl.querySelector("#subject-form"); // ← may be missing for students

  if (!$subjectForm) {
        console.info(
            "Subject widget: <form id='subject-form'> not found – " +
            "running in read‑only mode (student view)."
        );
    }

  async function loadYearChoices() {
    if (!$yearSelect) return;
    try {
      const resp = await fetch("/slm/api/subjects/year-choices/", {
        credentials: "same-origin",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json(); // {choices: [{value, label}, …]}

      $yearSelect.innerHTML = "";
      data.choices.forEach(c => {
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

  if (subject.is_owner) {
    const actions = document.createElement("div");
    actions.className = "subject-card__actions";

    const edit = document.createElement("a");
    edit.href = "#";
    edit.title = "Edit";
    edit.className = "subject-card__action js-modal-trigger";
    edit.dataset.url = `/slm/api/subjects/${subject.id}/edit-modal/`;
    edit.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 
               7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 
               0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
      </svg>`;
    actions.appendChild(edit);

    const del = document.createElement("a");
    del.href = "#";
    del.title = "Delete";
    del.className = "subject-card__action subject-card__action--delete js-modal-trigger";
    del.dataset.url = `/slm/api/subjects/${subject.id}/archive/`;
    del.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 
               0h2v8h-2V9zm-8 0h2v8H7V9z"/>
      </svg>`;
    actions.appendChild(del);

    card.appendChild(actions);
  }

  card.style.cursor = "pointer";

  card.addEventListener("click", e => {
    if (e.target.closest("a")) return;

    window.location.href = link.href;
  });

  return card;
}


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
      if (current)  li.classList.add("paginator__item--current");
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
      a.addEventListener("click", e => {
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

    if (meta.page + 2 < meta.total_pages - 1) {
      ul.appendChild(makeItem("…", null, false, false, true));
    }
    if (meta.total_pages > 1) {
      ul.appendChild(
        makeItem(String(meta.total_pages), null, false, meta.page === meta.total_pages)
      );
    }
    ul.appendChild(makeItem("→", meta.next_page_number, !meta.has_next));

    $list.parentNode.appendChild(nav);
  }

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
        $list.innerHTML = "<p>No subjects found. Please make sure your year level is set.</p>";
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

  async function create() {
    // Let the browser run its native validation first.
    if (typeof $subjectForm.reportValidity === "function" && !$subjectForm.reportValidity()) {
      return; // native UI will tell the user what’s missing.
    }

    const payload = {
      subject_code: $codeInput.value.trim().toUpperCase(),
      subject_name: $nameInput.value.trim(),
      // Year may be omitted for non‑teachers – keep it undefined if the <select> is missing.
      year: $yearSelect ? $yearSelect.value : undefined,
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
        showToast(`Subject "${created.subject_name}" created`, "success");

        $codeInput.value = "";
        $nameInput.value = "";
        if ($yearSelect && $yearSelect.options.length) $yearSelect.selectedIndex = 0;

        load();
      } else {
        const err = await resp.json();
        showToast(err.error || resp.statusText, "error");
      }
    } catch (e) {
      showToast(`Failed to create subject – ${e}`, "error");
    }
  }

    if ($subjectForm) {
        $subjectForm.addEventListener("submit", e => {
            e.preventDefault();
            create();
        });
    }

    loadYearChoices();
    load();
}
