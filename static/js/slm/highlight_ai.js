// static/js/slm/highlight_ai.js
// ---------------------------------------------------------------
// Highlight → Ask‑AI widget (occurrence‑aware)
// ---------------------------------------------------------------

import { csrftoken } from "./utils.js";

export function initHighlightAI(
  toolbar,
  moduleId,
  contentScope = ".module-content-card .module-content",
  apiBase = "/slm/api/modules/",
) {
  /* -----------------------------------------------------------------
   * 0️⃣ Abort early if we have no id or no API base (e.g. static pages)
   * ----------------------------------------------------------------- */
  const hasValidId = Number.isInteger(moduleId) && moduleId > 0;
  if (!hasValidId) {
    console.info(
      "[highlight_ai] No valid id supplied – highlight cache disabled.",
    );
  }

  /* -----------------------------------------------------------------
   * 1️⃣ Resolve the content root element
   * ----------------------------------------------------------------- */
  const contentRoot =
    typeof contentScope === "string"
      ? document.querySelector(contentScope)
      : contentScope;
  if (!contentRoot) return;

  // -----------------------------------------------------------
  // 1️⃣ Keep the *original* HTML that we received from the server.
  //    Every time a new query is added we will reset the container
  //    to this clean copy and then re‑apply **only the stored
  //    occurrences**.
  // -----------------------------------------------------------
  const _originalHtml = contentRoot.innerHTML;

  /* -----------------------------------------------------------------
   * 2️⃣ History UI elements
   * ----------------------------------------------------------------- */
  const historyList = document.getElementById("highlight-history-list");
  const historyCount = document.getElementById("highlight-history-count");
  const historyToggle = document.getElementById("highlight-history-toggle");
  const historyPopover = document.getElementById("highlight-history-popover");

  const historyEntries = []; // [{text,start,end,levels:[]}]
  let historyFocusTimer = null;

  // Reset any stale UI when the script initialises on a new page.
  if (historyList) historyList.innerHTML = "";
  if (historyCount) historyCount.textContent = "0 items";

  /* -----------------------------------------------------------------
   * 3️⃣ Normalise queries (lower‑case) – DB stores lower‑case
   * ----------------------------------------------------------------- */
  const normalise = (txt) => (txt || "").trim().toLowerCase();

  /* -----------------------------------------------------------------
   * 4️⃣ Internal storage – keyed by a *unique occurrence key*
   * ----------------------------------------------------------------- */
  const occurrenceKey = (q, s, e) => `${q}|${s}-${e}`; // q is lower‑cased

  const occurrences = new Map(); // key → {queryOrig,…}
  const pendingAiRequests = new Set();

  /* -----------------------------------------------------------------
   * 5️⃣ Helpers – compute offsets and selection data
   * ----------------------------------------------------------------- */
  // ----- text‑node walker (used for offset calculation) -------------
  const getTextNodes = () => {
    const walker = document.createTreeWalker(
      contentRoot,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          return node.nodeValue
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT;
        },
      },
    );

    const nodes = [];
    let node;
    while ((node = walker.nextNode())) {
      nodes.push(node);
    }
    return nodes;
  };

  // ----- compute a character offset for a container/offset pair --------
  const getBoundaryOffset = (container, offset) => {
    const nodes = getTextNodes();
    let total = 0;

    for (const node of nodes) {
      if (node === container) {
        return total + Math.min(Math.max(offset, 0), node.nodeValue.length);
      }

      // If the node is before the boundary, add its whole length.
      const range = document.createRange();
      try {
        range.setStart(contentRoot, 0);
        range.setEnd(node, node.nodeValue.length);
        const target = document.createRange();
        target.setStart(contentRoot, 0);
        target.setEnd(container, offset);
        if (range.compareBoundaryPoints(Range.END_TO_END, target) <= 0) {
          total += node.nodeValue.length;
        } else {
          break;
        }
      } catch {
        break; // safety net – should never happen
      }
    }
    return total;
  };

  const computeOffsets = (range) => ({
    start: getBoundaryOffset(range.startContainer, range.startOffset),
    end: getBoundaryOffset(range.endContainer, range.endOffset),
  });

  const getSelectionData = (range) => {
    const rawText = range.toString();
    const query = rawText.trim();
    if (!query) return null;

    const { start: rawStart, end: rawEnd } = computeOffsets(range);

    // Trim only leading/trailing whitespace from the *selection*
    const leading = rawText.length - rawText.trimStart().length;
    const trailing = rawText.length - rawText.trimEnd().length;
    const start = rawStart + leading;
    const end = rawEnd - trailing;

    if (end <= start) return null;
    return { query, start, end };
  };

  /* -----------------------------------------------------------------
   * 6️⃣ CSS class helper (highlight colour)
   * ----------------------------------------------------------------- */
  const getHighlightClassName = (occ) => {
    const simp = !!occ.simplified;
    const tech = !!occ.technical;
    if (simp && tech) return "highlight-marked highlight-marked--both";
    if (simp) return "highlight-marked highlight-marked--simplified";
    if (tech) return "highlight-marked highlight-marked--technical";
    return "highlight-marked";
  };

  const buildAnswerText = (occ) => {
    const parts = [];
    if (occ.simplifiedAnswer)
      parts.push(`Simplified:\n${occ.simplifiedAnswer}`);
    if (occ.technicalAnswer) parts.push(`Technical:\n${occ.technicalAnswer}`);
    if (occ.note) parts.push(`Annotation:\n${occ.note}`);
    return parts.join("\n\n");
  };

  /* -----------------------------------------------------------------
   * 7️⃣ UI helpers (history, tooltips, messages, …)
   * ----------------------------------------------------------------- */
  const showMessage = (container, text, type = "success") => {
    const old = container.querySelector(".annotation-message");
    if (old) old.remove();

    const msg = document.createElement("div");
    msg.className = `annotation-message annotation-message--${type}`;
    msg.textContent = text;
    msg.style.fontSize = "0.9em";
    msg.style.marginTop = "4px";
    msg.style.color = type === "error" ? "#d00" : "#080";

    container.appendChild(msg);
    setTimeout(() => {
      msg.style.transition = "opacity 0.4s";
      msg.style.opacity = "0";
      setTimeout(() => msg.remove(), 500);
    }, 1500);
  };

  const toggleHistoryPopover = () => {
    if (!historyPopover || !historyToggle) return;
    const next = historyPopover.hidden;
    historyPopover.hidden = !next;
    historyToggle.setAttribute("aria-expanded", String(!next));
  };

  const closeHistoryPopover = () => {
    if (!historyPopover || !historyToggle) return;
    historyPopover.hidden = true;
    historyToggle.setAttribute("aria-expanded", "false");
  };

  const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  const updateHistoryUI = () => {
    if (!historyList) return;
    historyList.innerHTML = "";

    if (historyEntries.length === 0) {
      const empty = document.createElement("li");
      empty.className = "module-content-history__item";
      empty.textContent = "No highlights yet.";
      historyList.appendChild(empty);
      if (historyCount) historyCount.textContent = "0 items";
      return;
    }

    // Newest first
    historyEntries
      .slice()
      .reverse()
      .forEach((entry) => {
        const li = document.createElement("li");
        li.className = "module-content-history__item";
        li.tabIndex = 0;

        const termSpan = document.createElement("span");
        termSpan.className = "module-content-history__text";
        termSpan.textContent = entry.text;

        const levelsDiv = document.createElement("div");
        levelsDiv.className = "module-content-history__levels";

        entry.levels.forEach((lvl) => {
          const lvlDiv = document.createElement("div");
          lvlDiv.className = "module-content-history__level-item";
          lvlDiv.textContent = capitalize(lvl);
          levelsDiv.appendChild(lvlDiv);
        });

        li.append(termSpan, levelsDiv);
        li.addEventListener("click", () =>
          focusHighlight(entry.start, entry.end),
        );
        li.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            focusHighlight(entry.start, entry.end);
          }
        });
        historyList.appendChild(li);
      });

    if (historyCount) {
      const n = historyEntries.length;
      historyCount.textContent = `${n} ${n === 1 ? "item" : "items"}`;
    }
  };

  const addHistoryEntry = (text, level, start, end) => {
    const clean = (text || "").trim();
    if (!clean) return;

    const existing = historyEntries.find(
      (e) => e.text === clean && e.start === start && e.end === end,
    );

    if (existing) {
      if (!existing.levels.includes(level)) existing.levels.push(level);
    } else {
      historyEntries.push({ text: clean, start, end, levels: [level] });
    }
    updateHistoryUI();
  };

  const clearHistoryFocus = () => {
    if (historyFocusTimer) {
      clearTimeout(historyFocusTimer);
      historyFocusTimer = null;
    }
    contentRoot
      .querySelectorAll(".highlight-history-focused")
      .forEach((s) => s.classList.remove("highlight-history-focused"));
  };

  const focusHighlight = (start, end) => {
    const selector = `.highlight-marked[data-start="${start}"][data-end="${end}"]`;
    const matches = Array.from(contentRoot.querySelectorAll(selector));
    if (!matches.length) return;
    clearHistoryFocus();
    matches.forEach((s) => s.classList.add("highlight-history-focused"));
    matches[0].scrollIntoView({ behavior: "smooth", block: "center" });
    closeHistoryPopover();
    historyFocusTimer = setTimeout(clearHistoryFocus, 2200);
  };

  /* -----------------------------------------------------------------
   * 8️⃣ Create / update occurrence structures
   * ----------------------------------------------------------------- */
  const getOrCreateOccurrence = (queryOrig, start, end) => {
    const queryLC = normalise(queryOrig);
    const key = occurrenceKey(queryLC, start, end);
    let occ = occurrences.get(key);
    if (!occ) {
      occ = {
        queryOrig,
        queryLC,
        start,
        end,
        simplified: false,
        technical: false,
        annotated: false,
        note: "",
        simplifiedAnswer: "",
        technicalAnswer: "",
      };
      occurrences.set(key, occ);
    }
    return occ;
  };

  const setOccurrenceState = (queryOrig, start, end, level) => {
    const occ = getOrCreateOccurrence(queryOrig, start, end);
    occ[level] = true;
    _refreshAllHighlights();
  };

  const setOccurrenceAnswer = (queryOrig, start, end, level, answer) => {
    const occ = getOrCreateOccurrence(queryOrig, start, end);
    if (level === "simplified") {
      occ.simplifiedAnswer = answer;
      occ.simplified = true;
    } else {
      occ.technicalAnswer = answer;
      occ.technical = true;
    }
    _refreshAllHighlights();
  };

  const setOccurrenceAnnotation = (queryOrig, start, end, note) => {
    const occ = getOrCreateOccurrence(queryOrig, start, end);
    occ.note = note;
    occ.annotated = true;
    _refreshAllHighlights();
  };

  /* -----------------------------------------------------------------
   * 9️⃣ Apply stored occurrences without touching the original HTML
   * ----------------------------------------------------------------- */
  const applyOccurrences = (occs) => {
    if (!occs.length) return;

    // ---- collect all text nodes (original DOM) --------------------
    const walker = document.createTreeWalker(
      contentRoot,
      NodeFilter.SHOW_TEXT,
      null,
      false,
    );
    const textNodes = [];
    let node;
    while ((node = walker.nextNode())) {
      textNodes.push(node);
    }

    // ---- filter & sort occurrences ---------------------------------
    const valid = occs
      .filter(
        (o) =>
          Number.isFinite(o.start) && Number.isFinite(o.end) && o.end > o.start,
      )
      .sort((a, b) => a.start - b.start || a.end - b.end);

    let globalOffset = 0;

    textNodes.forEach((tn) => {
      const txt = tn.nodeValue || "";
      const nodeStart = globalOffset;
      const nodeEnd = nodeStart + txt.length;

      // Find occurrences that intersect this text node
      const touching = valid.filter(
        (o) => o.start < nodeEnd && o.end > nodeStart,
      );
      if (!touching.length || !tn.parentNode) {
        globalOffset = nodeEnd;
        return;
      }

      const fragment = document.createDocumentFragment();
      let cursor = 0;

      touching.forEach((occ) => {
        const localStart = Math.max(0, occ.start - nodeStart);
        const localEnd = Math.min(txt.length, occ.end - nodeStart);
        if (localEnd <= localStart) return;

        // avoid overlap (user selections should never overlap)
        const safeStart = Math.max(localStart, cursor);
        if (safeStart > cursor) {
          fragment.appendChild(
            document.createTextNode(txt.slice(cursor, safeStart)),
          );
        }

        const selectedText = txt.slice(safeStart, localEnd);
        if (selectedText.length) {
          const span = document.createElement("span");
          span.className = getHighlightClassName(occ);
          span.dataset.highlightQuery = occ.queryOrig;
          span.dataset.start = String(occ.start);
          span.dataset.end = String(occ.end);
          span.dataset.answer = buildAnswerText(occ);
          span.dataset.highlightOccurrence = occurrenceKey(
            occ.queryLC,
            occ.start,
            occ.end,
          );
          span.dataset.highlightOccurrence = occurrenceKey(
            occ.queryLC,
            occ.start,
            occ.end,
          );
          span.textContent = selectedText;

          // attach the click handler (only once per span)
          attachHighlightEvents(span, occ.queryOrig);
          fragment.appendChild(span);
        }

        cursor = localEnd;
      });

      // trailing normal text
      if (cursor < txt.length) {
        fragment.appendChild(document.createTextNode(txt.slice(cursor)));
      }

      tn.parentNode.replaceChild(fragment, tn);
      globalOffset = nodeEnd;
    });
  };

  /* -----------------------------------------------------------------
   * 🔟 Refresh all highlights (re‑build from the stored map)
   * ----------------------------------------------------------------- */
  const refreshAllHighlightsImpl = () => {
    // restore the pristine HTML
    contentRoot.innerHTML = _originalHtml;

    // apply every stored occurrence
    const occs = Array.from(occurrences.values());
    applyOccurrences(occs);

    // mark first / middle / last fragments of a logical highlight
    contentRoot
      .querySelectorAll(".highlight-marked")
      .forEach((s) =>
        s.classList.remove(
          "highlight-fragment-first",
          "highlight-fragment-middle",
          "highlight-fragment-last",
        ),
      );

    const grouped = new Map();
    contentRoot
      .querySelectorAll(".highlight-marked[data-highlight-occurrence]")
      .forEach((span) => {
        const key = span.dataset.highlightOccurrence;
        if (!grouped.has(key)) grouped.set(key, []);
        grouped.get(key).push(span);
      });

    grouped.forEach((spans) => {
      if (spans.length === 1) {
        spans[0].classList.add(
          "highlight-fragment-first",
          "highlight-fragment-last",
        );
      } else {
        spans.forEach((s, i) => {
          if (i === 0) s.classList.add("highlight-fragment-first");
          else if (i === spans.length - 1)
            s.classList.add("highlight-fragment-last");
          else s.classList.add("highlight-fragment-middle");
        });
      }
    });
  };

  const _refreshAllHighlights = () => {
    refreshAllHighlightsImpl();
  };

  /* -----------------------------------------------------------------
   * 11️⃣ Tooltip handling (show / hide answer / annotation UI)
   * ----------------------------------------------------------------- */
  let activeTooltip = null;
  const removeTooltip = () => {
    if (activeTooltip) {
      activeTooltip.remove();
      activeTooltip = null;
    }
  };

  const fetchAiAnswer = async (query, level, start, end) => {
    const payload = {
      query,
      level,
      start_offset: start,
      end_offset: end,
    };
    const resp = await fetch(`${apiBase}${moduleId}/highlight/`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken,
      },
      body: JSON.stringify(payload),
    });
    let data = null;
    try {
      data = await resp.json();
    } catch {
      data = {};
    }
    if (!resp.ok)
      throw new Error(data?.error ?? `AI request failed (${resp.status})`);
    if (!data.answer) throw new Error("The AI did not return an explanation.");
    setOccurrenceAnswer(query, start, end, level, data.answer);
    return data;
  };

  // -----------------------------------------------------------------
  // Render the AI answer section (or a “Get …” button) inside a container
  // -----------------------------------------------------------------
  const renderAiSection = (query, start, end, container) => {
    const occ = getOrCreateOccurrence(query, start, end);
    ["simplified", "technical"].forEach((lvl) => {
      const lvlCap = capitalize(lvl);
      const wrapper = document.createElement("div");
      wrapper.className = "ai-answer-level";

      const storedAns =
        lvl === "simplified" ? occ.simplifiedAnswer : occ.technicalAnswer;
      if (storedAns) {
        wrapper.innerHTML = `
          <h4>${lvlCap} answer</h4>
          <div class="ai-answer-content">${renderMarkdown(storedAns)}</div>
        `;
      } else {
        const btn = document.createElement("button");
        btn.className = "ai-get-level";
        btn.textContent = `Get ${lvlCap} answer`;
        btn.addEventListener("click", async () => {
          const requestKey = `${normalise(query)}|${start}-${end}|${lvl}`;
          if (pendingAiRequests.has(requestKey)) return;
          pendingAiRequests.add(requestKey);
          btn.disabled = true;
          const old = btn.textContent;
          btn.textContent = "Thinking…";

          try {
            const data = await fetchAiAnswer(query, lvl, start, end);
            if (data && data.answer) {
              // Re‑render the whole AI section – now with the answer filled in
              container.innerHTML = "";
              renderAiSection(query, start, end, container);
            }
          } catch (err) {
            console.error("AI answer failed:", err);
            showMessage(
              wrapper,
              err.message ?? "Unable to generate an AI explanation.",
              "error",
            );
          } finally {
            pendingAiRequests.delete(requestKey);
            btn.textContent = old;
            btn.disabled = false;
          }
        });
        wrapper.appendChild(btn);
      }
      container.appendChild(wrapper);
    });
  };

  // -----------------------------------------------------------------
  // Render the annotation UI (textarea + save button)
  // -----------------------------------------------------------------
  const renderAnnotationSection = (query, start, end, container) => {
    const occ = getOrCreateOccurrence(query, start, end);
    const wrapper = document.createElement("div");
    wrapper.className = "annotation-edit";

    const existing = occ.note.replace(/</g, "&lt;");

    wrapper.innerHTML = `
      <textarea rows="3" class="annotation-textarea">${existing}</textarea>
      <button class="annotation-save">Save</button>
    `;

    const textarea = wrapper.querySelector(".annotation-textarea");
    const saveBtn = wrapper.querySelector(".annotation-save");

    saveBtn.addEventListener("click", async () => {
      const note = textarea.value.trim();
      if (!note) {
        showMessage(wrapper, "Annotation cannot be empty.", "error");
        return;
      }

      saveBtn.disabled = true;
      const old = saveBtn.textContent;
      saveBtn.textContent = "Saving…";

      try {
        const resp = await fetch(`${apiBase}${moduleId}/annotation/`, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken,
          },
          body: JSON.stringify({
            query,
            note,
            start_offset: start,
            end_offset: end,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error ?? "Failed");

        setOccurrenceAnnotation(query, start, end, data.note ?? note);
        textarea.classList.add("annotation-saved");
        setTimeout(() => textarea.classList.remove("annotation-saved"), 600);
      } catch (e) {
        console.error("Saving annotation failed:", e);
        showMessage(wrapper, "Could not save annotation.", "error");
      } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = old;
      }
    });

    container.appendChild(wrapper);
  };

  // -----------------------------------------------------------------
  // Show the tooltip (AI + annotation tabs) for a highlighted span
  // -----------------------------------------------------------------
  const showTooltip = (span) => {
    const query = span.dataset.highlightQuery;
    const start = Number(span.dataset.start);
    const end = Number(span.dataset.end);
    if (!query) return;

    // toggle if the same tooltip is already open
    if (
      activeTooltip &&
      activeTooltip.dataset.for === query &&
      activeTooltip.dataset.start === `${start}` &&
      activeTooltip.dataset.end === `${end}`
    ) {
      removeTooltip();
      return;
    }

    removeTooltip();

    const occKey = occurrenceKey(normalise(query), start, end);
    const occ = occurrences.get(occKey);

    const tip = document.createElement("div");
    tip.className = "highlight-answer-tooltip";
    tip.dataset.for = query;
    tip.dataset.start = `${start}`;
    tip.dataset.end = `${end}`;

    const header = document.createElement("div");
    header.className = "highlight-tooltip-header";

    const defaultTab = occ && occ.annotated ? "annotation" : "ai";

    header.innerHTML = `
      <button class="tooltip-tab ${defaultTab === "ai" ? "tooltip-tab--active" : ""}" data-target="ai">AI Answers</button>
      <button class="tooltip-tab ${defaultTab === "annotation" ? "tooltip-tab--active" : ""}" data-target="annotation">Annotations</button>
    `;

    tip.appendChild(header);
    const body = document.createElement("div");
    body.className = "highlight-tooltip-body";
    tip.appendChild(body);

    const renderSection = (section) => {
      body.innerHTML = "";
      if (section === "ai") {
        renderAiSection(query, start, end, body);
      } else {
        renderAnnotationSection(query, start, end, body);
      }
    };

    renderSection(defaultTab);

    // toggle AI / annotation tabs
    header.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-target]");
      if (!btn) return;
      header
        .querySelectorAll(".tooltip-tab")
        .forEach((t) => t.classList.toggle("tooltip-tab--active", t === btn));
      renderSection(btn.dataset.target);
    });

    // keep clicks inside the tooltip from bubbling to the document (which would close it)
    tip.addEventListener("mousedown", (e) => e.stopPropagation());

    document.body.appendChild(tip);
    activeTooltip = tip;

    // Position it
    const rect = span.getBoundingClientRect();
    const maxW = Math.min(340, window.innerWidth - 24);
    const left = Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - maxW - 8,
    );
    const top = rect.bottom + window.scrollY + 8;

    tip.style.top = `${top}px`;
    tip.style.left = `${Math.max(8, left)}px`;
    tip.style.maxWidth = `${maxW}px`;
  };

  // -----------------------------------------------------------------
  // Attach click (and keyboard) handling to a highlight span
  // -----------------------------------------------------------------
  const attachHighlightEvents = (span, query) => {
    if (span.dataset.clickBound === "true") return;
    span.addEventListener("click", (e) => {
      e.stopPropagation(); // prevent document mouseup handling
      showTooltip(span);
    });
    span.setAttribute("tabindex", "0");
    span.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        showTooltip(span);
      }
    });
    span.dataset.clickBound = "true";
  };

  /* -----------------------------------------------------------------
   * 12️⃣ UI – Choice widget (Ask AI / Add annotation)
   * ----------------------------------------------------------------- */
  const createChoiceWidget = (range) => {
    const choice = document.createElement("div");
    choice.className = "highlight-choice";
    choice.innerHTML = `
      <p class="highlight-choice__text">What would you like to do?</p>
      <button class="choice-ask-ai">Ask AI</button>
      <button class="choice-annotate">Add annotation</button>
    `;
    document.body.appendChild(choice);

    // stop mouse / touch events from bubbling up to the document’s
    // global `mouseup` / `touchend` listener that would otherwise
    // re‑create the widget.
    choice.addEventListener("mousedown", (e) => e.stopPropagation());
    choice.addEventListener("touchstart", (e) => e.stopPropagation());

    const rect = range.getBoundingClientRect();
    const top = rect.bottom + window.scrollY + 6;
    const left = Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - choice.offsetWidth - 8,
    );
    choice.style.top = `${top}px`;
    choice.style.left = `${left}px`;

    const clickOutside = (e) => {
  if (!choice) return;            // guard
  if (!choice.contains(e.target)) {
    choice.remove();
    document.removeEventListener("mousedown", clickOutside);
    document.removeEventListener("touchstart", clickOutside);
    choiceWidget = null;
    window.getSelection().removeAllRanges();
  }
};
document.addEventListener("mousedown", clickOutside);
document.addEventListener("touchstart", clickOutside);

    // -----------------------------------------------------------------
    // Ask‑AI button
    // -----------------------------------------------------------------
    choice.querySelector(".choice-ask-ai").addEventListener("click", () => {
      choice.remove();
      document.removeEventListener("mousedown", clickOutside);
      document.removeEventListener("touchstart", clickOutside);
      // Use the *same* Range object – it still knows the exact offsets.
      mini = createAIMiniWidget(range);
    });

    // -----------------------------------------------------------------
    // Annotation button
    // -----------------------------------------------------------------
    choice.querySelector(".choice-annotate").addEventListener("click", () => {
      choice.remove();
      document.removeEventListener("mousedown", clickOutside);
      document.removeEventListener("touchstart", clickOutside);
      mini = createAnnotationWidget(range);
    });

    // keep a reference so we can know “we are inside a choice widget”
    choiceWidget = choice;
    return choice;
  };
  // keep a global reference for the early‑exit check
  let choiceWidget = null;

  /* -----------------------------------------------------------------
   * 13️⃣ Mini‑AI widget (level selector + “Get answer” button)
   * ----------------------------------------------------------------- */
  /* -----------------------------------------------------------------
   * 13️⃣ Mini‑AI widget (level selector + “Get answer” button)
   * ----------------------------------------------------------------- */
  const createAIMiniWidget = (range) => {
    /* -------------------------------------------------------------
     * Use the **global** `mini` variable (declared as `let mini = null;`
     * at the top of the file) instead of creating a new `const mini`.
     * ------------------------------------------------------------- */
    mini = document.createElement("div"); // <-- global mutable reference
    mini.className = "ai-mini";
    mini.innerHTML = `
    <select class="ai-level">
      <option value="simplified">Simplified</option>
      <option value="technical">Technical</option>
    </select>
    <button class="ai-get">Get answer</button>
    <div class="ai-answer hidden"></div>
  `;
    document.body.appendChild(mini);

    /* -------------------------------------------------------------
     * Stop the click/touch from bubbling up to the document‑level
     * `mouseup` / `touchend` handler that would otherwise recreate the
     * choice widget.
     * ------------------------------------------------------------- */
    mini.addEventListener("mousedown", (e) => e.stopPropagation());
    mini.addEventListener("touchstart", (e) => e.stopPropagation());

    /* -------------------------------------------------------------
     * Position the widget just below the original selection range.
     * ------------------------------------------------------------- */
    const rect = range.getBoundingClientRect();
    mini.style.top = `${rect.bottom + window.scrollY + 6}px`;
    mini.style.left = `${Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - mini.offsetWidth - 8,
    )}px`;

    /* -------------------------------------------------------------
     * Click‑outside handling – when the user taps anywhere else we
     * remove the mini widget, clear the global reference and also clear
     * the native selection (so the page no longer thinks a new
     * highlight was made).
     * ------------------------------------------------------------- */
    /* -------------------------------------------------------------
 * Click‑outside handling – when the user taps anywhere else we
 * remove the mini widget, clear the global reference and also clear
 * the native selection (so the page no longer thinks a new
 * highlight was made).
 * ------------------------------------------------------------- */
const clickOutside = (e) => {
  // The overlay may already have been removed elsewhere.
  if (!mini) return;               // <‑‑ guard

  if (!mini.contains(e.target)) {
    mini.remove();
    document.removeEventListener("mousedown", clickOutside);
    document.removeEventListener("touchstart", clickOutside);
    mini = null;
    window.getSelection().removeAllRanges();
  }
};
    document.addEventListener("mousedown", clickOutside);
    document.addEventListener("touchstart", clickOutside);

    /* -------------------------------------------------------------
     * Wire the “Get answer” button.
     * ------------------------------------------------------------- */
    const btn = mini.querySelector(".ai-get");
    const levelSelect = mini.querySelector(".ai-level");

    btn.addEventListener("click", async () => {
      const level = levelSelect.value;
      const selData = getSelectionData(range);
      if (!selData) return;
      const { query, start, end } = selData;

      btn.disabled = true;
      const old = btn.textContent;
      btn.textContent = "Thinking…";

      try {
        const data = await fetchAiAnswer(query, level, start, end);
        if (data && data.answer) {
          /* re‑render the whole answer area now that we have the
           cached answer stored in `occurrences` */
          const answerContainer = mini.querySelector(".ai-answer");
          renderAiSection(query, start, end, answerContainer);
        }
      } catch (err) {
        console.error("AI request failed:", err);
        renderAnswer(
          mini,
          "<em>Sorry – the AI service could not be reached.</em>",
          false,
        );
      } finally {
        btn.textContent = old;
        btn.disabled = false;
        /* After a successful request we also clear the native selection
         – it would otherwise trigger the global `onSelectionDone`
         handler again on the next tap. */
        window.getSelection().removeAllRanges();
      }
    });

    return mini; // the global `mini` now holds the same element
  };

  /* -----------------------------------------------------------------
   * 14️⃣ Annotation widget (textarea + Save)
   * ----------------------------------------------------------------- */
  const createAnnotationWidget = (range) => {
    const ann = document.createElement("div");
    ann.className = "annotation-widget";
    document.body.appendChild(ann);

    // stop propagation
    ann.addEventListener("mousedown", (e) => e.stopPropagation());
    ann.addEventListener("touchstart", (e) => e.stopPropagation());

    const rect = range.getBoundingClientRect();
    ann.style.top = `${rect.bottom + window.scrollY + 6}px`;
    ann.style.left = `${Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - ann.offsetWidth - 8,
    )}px`;

    const selection = getSelectionData(range);
    if (!selection) {
      ann.remove();
      return ann;
    }
    const { query, start, end } = selection;
    ann.dataset.startOffset = String(start);
    ann.dataset.endOffset = String(end);

    renderAnnotationSection(query, start, end, ann);

    const clickOutside = (e) => {
  if (!ann) return;               // guard – the widget may already be gone
  if (!ann.contains(e.target)) {
    ann.remove();
    document.removeEventListener("mousedown", clickOutside);
    document.removeEventListener("touchstart", clickOutside);
    window.getSelection().removeAllRanges();
  }
};
document.addEventListener("mousedown", clickOutside);
document.addEventListener("touchstart", clickOutside);
    return ann;
  };

  /* -----------------------------------------------------------------
   * 15️⃣ Markdown → HTML (unchanged, kept for completeness)
   * ----------------------------------------------------------------- */
  const escapeHtml = (v) =>
    v
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const inlineFormatting = (txt) =>
    txt
      .replace(
        /!\[([^\]]*)\]\(([^)]+)\)/g,
        (_, a, s) =>
          `<span class="inline-image"><img src="${escapeHtml(s)}" alt="${escapeHtml(a)}"></span>`,
      )
      .replace(
        /\[([^\]]+)\]\(([^)]+)\)/g,
        (_, l, h) =>
          `<a href="${escapeHtml(h)}" target="_blank" rel="noopener noreferrer">${escapeHtml(l)}</a>`,
      )
      .replace(
        /\*\*([^*]+)\*\*/g,
        (_, b) => `<strong>${escapeHtml(b)}</strong>`,
      )
      .replace(/\*([^*]+)\*/g, (_, i) => `<em>${escapeHtml(i)}</em>`)
      .replace(/`([^`]+)`/g, (_, c) => `<code>${escapeHtml(c)}</code>`);

  const renderMarkdown = (txt) => {
    if (!txt) return "";
    const lines = escapeHtml(txt).split(/\r?\n/);
    let html = "";
    let listType = null;
    let listOpen = false;
    let tableRows = [];
    let inTable = false;

    const closeList = () => {
      if (listOpen) {
        html += listType === "ol" ? "</ol>" : "</ul>";
        listOpen = false;
        listType = null;
      }
    };
    const flushTable = () => {
      if (!inTable || !tableRows.length) return;
      const rows = tableRows
        .map((r) =>
          r
            .replace(/^\||\|$/g, "")
            .split("|")
            .map((c) => c.trim()),
        )
        .filter((r) => r.length);
      const header = rows[0] || [];
      const sep = rows[1] || [];
      const body = rows.slice(2);
      const isTable = sep.every((c) => /^:?-+:?$/.test(c));
      if (isTable) {
        html += '<table class="message-table"><thead><tr>';
        header.forEach((c) => (html += `<th>${inlineFormatting(c)}</th>`));
        html += "</tr></thead><tbody>";
        body.forEach((r) => {
          html += "<tr>";
          r.forEach((c) => (html += `<td>${inlineFormatting(c)}</td>`));
          html += "</tr>";
        });
        html += "</tbody></table>";
      } else {
        tableRows.forEach((r) => (html += `<p>${inlineFormatting(r)}</p>`));
      }
      tableRows = [];
      inTable = false;
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const t = line.trim();

      const heading = t.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        closeList();
        flushTable();
        const lvl = Math.min(6, heading[1].length);
        html += `<h${lvl}>${inlineFormatting(heading[2])}</h${lvl}>`;
        continue;
      }
      if (/^(---|\*\*\*|___)\s*$/.test(t)) {
        closeList();
        flushTable();
        html += '<hr class="message-hr"/>';
        continue;
      }
      if (/^>\s?/.test(t)) {
        closeList();
        flushTable();
        html += `<blockquote>${inlineFormatting(t.replace(/^>\s?/, ""))}</blockquote>`;
        continue;
      }
      if (/^```/.test(t)) {
        closeList();
        flushTable();
        let code = "";
        i++;
        while (i < lines.length && !/^```/.test(lines[i].trim())) {
          code += lines[i] + "\n";
          i++;
        }
        html += `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
        continue;
      }
      if (/^!\[.*\]\(.*\)$/.test(t)) {
        closeList();
        flushTable();
        html += t.replace(
          /!\[([^\]]*)\]\(([^)]+)\)/g,
          (_, a, s) =>
            `<div class="message-image"><img src="${escapeHtml(s)}" alt="${escapeHtml(a)}"></div>`,
        );
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line)) {
        closeList();
        inTable = true;
        tableRows.push(line);
        continue;
      }
      if (inTable && t === "") {
        flushTable();
        continue;
      }
      if (/^\d+\.\s+/.test(t)) {
        flushTable();
        const txt = t.replace(/^\d+\.\s+/, "");
        if (!listOpen || listType !== "ol") {
          closeList();
          listType = "ol";
          listOpen = true;
          html += "<ol>";
        }
        html += `<li>${inlineFormatting(txt)}</li>`;
        continue;
      }
      if (/^[-*+]\s+/.test(t)) {
        flushTable();
        const txt = t.replace(/^[-*+]\s+/, "");
        if (!listOpen || listType !== "ul") {
          closeList();
          listType = "ul";
          listOpen = true;
          html += "<ul>";
        }
        html += `<li>${inlineFormatting(txt)}</li>`;
        continue;
      }
      if (t === "") {
        closeList();
        flushTable();
        html += "<p></p>";
        continue;
      }
      closeList();
      flushTable();
      html += `<p>${inlineFormatting(t)}</p>`;
    }
    closeList();
    flushTable();
    return html;
  };

  const renderAnswer = (miniWidget, html, cached) => {
    const box = miniWidget.querySelector(".ai-answer");
    box.innerHTML = `
      ${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ""}
      <div class="ai-answer-content">${renderMarkdown(html)}</div>
    `;
    box.classList.remove("hidden");
  };

  /* -----------------------------------------------------------------
   * 16️⃣ Bind selection → choice widget
   * ----------------------------------------------------------------- */
  let mini = null;

  const isSelectionWithinContent = (sel) => {
    if (!sel || sel.rangeCount === 0) return false;
    const range = sel.getRangeAt(0);
    const up = (node) => {
      while (node) {
        if (node === contentRoot) return true;
        node = node.parentNode;
      }
      return false;
    };
    return up(range.startContainer) && up(range.endContainer);
  };

  const onSelectionDone = (e) => {
    // --------------------------------------------------------------
    // 1️⃣  Guard: ignore any click that originates from an overlay UI.
    // --------------------------------------------------------------
    if (
      e.target.closest(".highlight-choice") ||
      e.target.closest(".ai-mini") ||
      e.target.closest(".annotation-widget") ||
      e.target.closest(".highlight-answer-tooltip")
    ) {
      return;
    }

    // --------------------------------------------------------------
    // 2️⃣  Normal selection handling (unchanged)
    // --------------------------------------------------------------
    const sel = window.getSelection();
    const txt = sel.toString().trim();

    // Hide history pop‑over if we hit outside of it.
    if (
      historyPopover &&
      !historyPopover.hidden &&
      !historyPopover.contains(e.target) &&
      !historyToggle?.contains(e.target)
    ) {
      closeHistoryPopover();
    }

    // If the click is inside the toolbar or an already open mini widget,
    // ignore – we don’t want to re‑open the choice.
    if (toolbar.contains(e.target) || (mini && mini.contains(e.target))) {
      return;
    }

    if (!txt || !isSelectionWithinContent(sel)) {
      // No selection – clean up any UI & hide toolbar
      if (mini) {
        mini.remove();
        mini = null;
      }
      toolbar.style.display = "none";
      return;
    }

    // Hide the toolbar - it will be shown again only after a new range.
    toolbar.style.display = "none";

    const range = sel.getRangeAt(0);

    // Remove any previous mini‑widget before we open a new one.
    if (mini) {
      mini.remove();
      mini = null;
    }

    // Finally create the choice widget.  The returned element is stored
    // in the global `choiceWidget` variable so that the early‑exit guard
    // above can recognise clicks that belong to it.
    mini = createChoiceWidget(range);
    // In the original code the variable was called `mini`; we keep the
    // name because the rest of the script already uses it.
  };

  /* -----------------------------------------------------------------
   * 17️⃣ Pre‑load cached answers & annotations (unchanged)
   * ----------------------------------------------------------------- */
  const preloadExistingData = async () => {
    if (!hasValidId) return;
    try {
      const [answersResp, annResp] = await Promise.all([
        fetch(`${apiBase}${moduleId}/highlight/`),
        fetch(`${apiBase}${moduleId}/annotation/`),
      ]);

      // ----- cached answers -------------------------------------------------
      if (answersResp.ok) {
        const data = await answersResp.json();
        (data.answers || []).forEach((item) => {
          const query = (item.query || "").trim();
          const start = item.start_offset;
          const end = item.end_offset;
          if (!query || start == null || end == null) return;
          const occ = getOrCreateOccurrence(query, start, end);
          if (item.answer) {
            if (item.answer.simplified) {
              occ.simplifiedAnswer = item.answer.simplified;
              occ.simplified = true;
              addHistoryEntry(query, "simplified", start, end);
            }
            if (item.answer.technical) {
              occ.technicalAnswer = item.answer.technical;
              occ.technical = true;
              addHistoryEntry(query, "technical", start, end);
            }
          }
        });
      }

      // ----- saved annotations ---------------------------------------------
      if (annResp.ok) {
        const annData = await annResp.json();
        (annData.annotations || []).forEach((a) => {
          const query = (a.query || "").trim();
          const start = a.start_offset;
          const end = a.end_offset;
          if (!query || start == null || end == null) return;
          setOccurrenceAnnotation(query, start, end, a.note);
          addHistoryEntry(query, "annotation", start, end);
        });
      }

      // rebuild UI once everything is loaded
      _refreshAllHighlights();
    } catch (e) {
      console.warn("Could not preload highlights/annotations:", e);
    }
  };

  /* -----------------------------------------------------------------
   * 18️⃣ Initialise everything
   * ----------------------------------------------------------------- */
  preloadExistingData();
  updateHistoryUI();

  if (historyToggle) {
    historyToggle.addEventListener("click", (ev) => {
      ev.stopPropagation();
      toggleHistoryPopover();
    });
  }

  // -----------------------------------------------------------------
  // Mouse / touch handling (global)
  // -----------------------------------------------------------------
  document.addEventListener("mouseup", onSelectionDone);
  document.addEventListener("touchend", (e) =>
    setTimeout(() => onSelectionDone(e), 10),
  );

  // -----------------------------------------------------------------
  // Hide tooltips / mini‑widgets when clicking elsewhere
  // -----------------------------------------------------------------
  document.addEventListener("mousedown", (e) => {
    if (activeTooltip && !activeTooltip.contains(e.target)) removeTooltip();
    if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
      mini.remove();
      mini = null;
    }
    if (!toolbar.contains(e.target)) toolbar.style.display = "none";
  });

  document.addEventListener("touchstart", (e) => {
    if (activeTooltip && !activeTooltip.contains(e.target)) removeTooltip();
    if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
      mini.remove();
      mini = null;
    }
    if (!toolbar.contains(e.target)) toolbar.style.display = "none";
  });

  // -----------------------------------------------------------------
  // Keep the toolbar hidden when the selection collapses
  // -----------------------------------------------------------------
  /* -----------------------------------------------------------------
   * 22️⃣ Keep the overlay alive while the user is typing in it.
   * ----------------------------------------------------------------- */
  /* -----------------------------------------------------------------
 * 22️⃣ Keep the overlay alive while the user is typing in it.
 * ----------------------------------------------------------------- */
document.addEventListener("selectionchange", () => {
  const sel = window.getSelection();

  // “empty” means no characters (or only whitespace) are selected
  const selectionIsEmpty = !sel || !sel.toString().trim();

  // If an overlay (annotation‑widget **or** ai‑mini) is open **and**
  // the element that currently owns focus is inside that overlay,
  // we must **not** hide it.
  if (
    selectionIsEmpty &&
    mini &&                                            // an overlay exists
    (mini.classList.contains("annotation-widget") ||
      mini.classList.contains("ai-mini")) &&
    document.activeElement &&
    mini.contains(document.activeElement)
  ) {
    // user just gave focus to the textarea / a button inside the widget
    // → keep the widget on screen
    return;
  }

  // Normal case – empty selection → hide everything
  if (selectionIsEmpty) {
    if (mini) {
      mini.remove();
      mini = null;
    }
    toolbar.style.display = "none";
  }
});
}