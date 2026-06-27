import { csrftoken } from "./utils.js";

/**
 * Initialise the “self‑learning modules” widget.
 * Expected data‑attributes on the root element:
 *   data-list-url   → "/slm/api/subjects/"
 *   data-create-url → "/slm/api/subjects/create/"
 */
export function initSubjectWidget(rootEl) {
  // -----------------------------------------------------------------
  // URLs coming from the template
  // -----------------------------------------------------------------
  const listUrl = rootEl.dataset.listUrl; // will receive ?page=
  const createUrl = rootEl.dataset.createUrl;
  const updateTpl = rootEl.dataset.updateUrl; // "/slm/api/subjects/{id}/"
  const deleteTpl = rootEl.dataset.deleteUrl; // "/slm/api/subjects/{id}/delete/"

  // -----------------------------------------------------------------
  // DOM shortcuts
  // -----------------------------------------------------------------
  const $list = rootEl.querySelector("#subject-list");
  const $status = rootEl.querySelector("#status");

  // Optional create‑form (visible only for logged‑in users)
  const $codeInput = rootEl.querySelector("#code-input");
  const $nameInput = rootEl.querySelector("#name-input");
  const $addBtn = rootEl.querySelector("#add-btn");

  // -----------------------------------------------------------------
// Helper – render a *single* subject card (now clickable)
// -----------------------------------------------------------------
function renderCard(subject) {
    const card = document.createElement('div');
    card.className = 'subject-card';
    card.dataset.id = subject.id;

    const contentLink = document.createElement('a');
    contentLink.href = subject.detail_url;
    contentLink.className = 'subject-card-link';
    contentLink.setAttribute('aria-label', `Open ${subject.subject_code}`);

    const h1 = document.createElement('h1');
    h1.textContent = subject.subject_code;
    contentLink.appendChild(h1);

    const p = document.createElement('p');
    p.textContent = subject.subject_name;
    contentLink.appendChild(p);

    const i = document.createElement('i');
    i.textContent = `By ${subject.author_name}`;
    contentLink.appendChild(i);

    card.appendChild(contentLink);

    if (subject.is_owner) {
        const actionBar = document.createElement('div');
        actionBar.className = 'subject-card__actions';

        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'subject-card__action';
        editBtn.title = 'Edit';
        editBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 8.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
        editBtn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            editSubject(subject);
        });
        actionBar.appendChild(editBtn);

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'subject-card__action subject-card__action--delete';
        delBtn.title = 'Delete';
        delBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm2 6h2v8h-2V9zm4 0h2v8h-2V9zm-8 0h2v8H7V9z"/></svg>';
        delBtn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            deleteSubject(subject.id);
        });
        actionBar.appendChild(delBtn);

        card.appendChild(actionBar);
    }

    return card;
}

  // ---------------------------------------------------------------
  // Helper – build the paginator UI from the meta object received
  // ---------------------------------------------------------------
  function renderPaginator(meta) {
    // Remove any old paginator that might be there
    const old = rootEl.querySelector(".paginator");
    if (old) old.remove();

    // -----------------------------------------------------------------
    // 1️⃣  <nav class="paginator"> … </nav>
    // -----------------------------------------------------------------
    const nav = document.createElement("nav");
    nav.className = "paginator";
    nav.setAttribute("aria-label", "Search results pagination");

    const ul = document.createElement("ul");
    ul.className = "paginator__list";
    nav.appendChild(ul);

    /**
     * makeItem(label, targetPage?, disabled?, current?, isEllipsis?)
     *
     * *label* – the text that appears inside the link (e.g. "←", "1", "…").
     * *targetPage* – the **numeric** page we want to load when the item is
     *                clicked.  If omitted we will try to infer it from the
     *                label (only for the normal page‑number links).
     * *disabled* – render as a disabled item.
     * *current* – render as the current page (no link, just a <span>).
     * *isEllipsis* – render as the “…’’ item.
     */
    const makeItem = (
      label,
      targetPage = null,
      disabled = false,
      current = false,
      isEllipsis = false,
    ) => {
      const li = document.createElement("li");
      li.className = "paginator__item";
      if (disabled) li.classList.add("paginator__item--disabled");
      if (current) li.classList.add("paginator__item--current");
      if (isEllipsis) li.classList.add("paginator__item--ellipsis");

      // -------------------------------------------------------------
      // Current page → plain <span>
      // -------------------------------------------------------------
      if (current) {
        const span = document.createElement("span");
        span.className = "paginator__link";
        span.textContent = label;
        li.appendChild(span);
        return li;
      }

      // -------------------------------------------------------------
      // Ellipsis → plain <span> (no link)
      // -------------------------------------------------------------
      if (isEllipsis) {
        const span = document.createElement("span");
        span.className = "paginator__link";
        span.textContent = label;
        li.appendChild(span);
        return li;
      }

      // -------------------------------------------------------------
      // Normal link (arrow or number)
      // -------------------------------------------------------------
      const a = document.createElement("a");
      a.className = "paginator__link";
      a.href = "#";
      a.textContent = label;
      if (disabled) a.setAttribute("tabindex", "-1");

      // Click handler – only if we have a *real* page to go to
      a.addEventListener("click", (e) => {
        e.preventDefault();
        // If a specific targetPage was given, use it.
        // Otherwise try to parse the label (this works for numeric pages).
        const pageToLoad = targetPage !== null ? targetPage : Number(label);
        if (!isNaN(pageToLoad) && pageToLoad !== meta.page) {
          load(pageToLoad);
        }
      });

      li.appendChild(a);
      return li;
    };

    // -------------------------------------------------------------
    // 2️⃣  Prev arrow
    // -------------------------------------------------------------
    ul.appendChild(
      makeItem(
        "←",
        meta.previous_page_number, // ← target page
        !meta.has_previous,
      ), // disabled?
    );

    // -------------------------------------------------------------
    // 3️⃣  Page numbers – show up to 5 pages around the current one
    // -------------------------------------------------------------
    const total = meta.total_pages;
    const cur = meta.page;

    // always show first page
    ul.appendChild(makeItem("1", null, false, cur === 1));

    // gap between first page and the first inner page?
    if (cur - 2 > 2) {
      ul.appendChild(makeItem("…", null, false, false, true));
    }

    // inner window (max 5 total, centred on current)
    const start = Math.max(2, cur - 1);
    const end = Math.min(total - 1, cur + 1);
    for (let i = start; i <= end; i++) {
      if (i !== 1 && i !== total) {
        ul.appendChild(makeItem(String(i), null, false, cur === i));
      }
    }

    // another gap before the last page?
    if (cur + 2 < total - 1) {
      ul.appendChild(makeItem("…", null, false, false, true));
    }

    // always show last page (if there is more than one page)
    if (total > 1) {
      ul.appendChild(makeItem(String(total), null, false, cur === total));
    }

    // -------------------------------------------------------------
    // 4️⃣  Next arrow
    // -------------------------------------------------------------
    ul.appendChild(
      makeItem(
        "→",
        meta.next_page_number, // → target page
        !meta.has_next,
      ), // disabled?
    );

    // Insert the paginator after the list (or wherever you like)
    $list.parentNode.appendChild(nav);
  }

  // -----------------------------------------------------------------
  // 1️⃣  LOAD – GET a specific page (default = 1)
  // -----------------------------------------------------------------
  async function load(page = 1) {
    try {
      const url = `${listUrl}?page=${page}`;
      const resp = await fetch(url, { credentials: "same-origin" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const payload = await resp.json(); // {results: [...], page:…, total_pages:…, …}

      // ---- Render the cards -------------------------------------------------
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

      // ---- Render (or replace) the paginator -------------------------------
      renderPaginator(payload);
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // 2️⃣  CREATE – POST a new subject (unchanged)
  // -----------------------------------------------------------------
  async function create() {
    if (!$codeInput || !$nameInput) return;

    const payload = {
      subject_code: $codeInput.value.trim(),
      subject_name: $nameInput.value.trim(),
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
        load(); // reload current page (still page 1)
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // 3️⃣  UPDATE – PUT a single subject (owner only) – unchanged
  // -----------------------------------------------------------------
  async function editSubject(subject) {
    const newCode = prompt("New code (blank = keep old)", subject.subject_code);
    const newName = prompt("New name (blank = keep old)", subject.subject_name);
    if (newCode === null && newName === null) return; // cancelled

    const payload = {};
    if (newCode !== null && newCode !== "")
      payload.subject_code = newCode.trim();
    if (newName !== null && newName !== "")
      payload.subject_name = newName.trim();
    if (Object.keys(payload).length === 0) return; // nothing to send

    const url = updateTpl.replace("{id}", subject.id);

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
        $status.textContent = `✅ Updated #${subject.id}`;
        load(); // keep the same page
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // 4️⃣  DELETE – DELETE a subject (owner only) – unchanged
  // -----------------------------------------------------------------
  async function deleteSubject(pk) {
    if (!confirm("Delete this subject?")) return;
    const url = deleteTpl.replace("{id}", pk);
    try {
      const resp = await fetch(url, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrftoken },
      });
      if (resp.status === 204) {
        $status.textContent = "✅ Deleted";
        load(); // keep the same page (or fallback to last page)
      } else {
        const err = await resp.json();
        $status.textContent = `❌ ${err.error || resp.statusText}`;
      }
    } catch (e) {
      $status.textContent = `❌ ${e}`;
    }
  }

  // -----------------------------------------------------------------
  // UI bindings
  // -----------------------------------------------------------------
  if ($addBtn) $addBtn.addEventListener("click", create);
  load(); // initial load → page 1
}
