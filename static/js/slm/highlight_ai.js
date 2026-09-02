// static/js/slm/highlight_ai.js

// ---------------------------------------------------------------
// Highlight → Ask-AI widget (occurrence-aware)
// ---------------------------------------------------------------

import { csrftoken } from "./utils.js";

export function initHighlightAI(
  toolbar,
  moduleId,
  contentScope = ".module-content-card .module-content",
  apiBase = "/slm/api/modules/",
) {
  // ---------------------------------------------------------------
  // 0. Validate module ID
  // ---------------------------------------------------------------

  const hasValidId = Number.isInteger(moduleId) && moduleId > 0;

  if (!hasValidId) {
    console.info(
      "[highlight_ai] No valid id supplied – highlight cache disabled.",
    );
  }

  // ---------------------------------------------------------------
  // 1. Resolve content root
  // ---------------------------------------------------------------

  const contentRoot =
    typeof contentScope === "string"
      ? document.querySelector(contentScope)
      : contentScope;

  if (!contentRoot) return;

  // Keep the pristine server HTML.
  const _originalHtml = contentRoot.innerHTML;

  // ---------------------------------------------------------------
  // 2. History UI
  // ---------------------------------------------------------------

  const historyList = document.getElementById("highlight-history-list");

  const historyCount = document.getElementById("highlight-history-count");

  const historyToggle = document.getElementById("highlight-history-toggle");

  const historyPopover = document.getElementById("highlight-history-popover");

  const historyEntries = [];

  let historyFocusTimer = null;

  if (historyList) historyList.innerHTML = "";

  if (historyCount) {
    historyCount.textContent = "0 items";
  }

  // ---------------------------------------------------------------
  // 3. Normalisation
  // ---------------------------------------------------------------

  const normalise = (txt) => (txt || "").trim().toLowerCase();

  // ---------------------------------------------------------------
  // 4. Occurrence storage
  // ---------------------------------------------------------------

  const occurrenceKey = (q, s, e) => `${q}|${s}-${e}`;

  const occurrences = new Map();

  const pendingAiRequests = new Set();

  // ---------------------------------------------------------------
  // 5. Selection state
  // ---------------------------------------------------------------

  /*
   * IMPORTANT:
   *
   * `range` captured during the initial double tap is NOT treated
   * as the permanent selection.
   *
   * Mobile browsers update the native selection while the user
   * drags the selection handles.
   *
   * selectionchange is therefore used to keep this snapshot current.
   */

  let latestSelectionRange = null;

  let mini = null;

  let choiceWidget = null;

  /*
   * True while the user is physically manipulating a native
   * selection. This prevents our document-level touch handlers
   * from destroying the selection during handle dragging.
   */
  let selectionInteractionActive = false;

  // ---------------------------------------------------------------
  // 6. Text-node helpers
  // ---------------------------------------------------------------

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

  // ---------------------------------------------------------------
  // 7. Boundary offsets
  // ---------------------------------------------------------------

  const getBoundaryOffset = (container, offset) => {
    const nodes = getTextNodes();

    let total = 0;

    for (const node of nodes) {
      if (node === container) {
        return total + Math.min(Math.max(offset, 0), node.nodeValue.length);
      }

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
        break;
      }
    }

    return total;
  };

  const computeOffsets = (range) => ({
    start: getBoundaryOffset(range.startContainer, range.startOffset),

    end: getBoundaryOffset(range.endContainer, range.endOffset),
  });

  // ---------------------------------------------------------------
  // 8. Check whether selection belongs to content
  // ---------------------------------------------------------------

  const isSelectionWithinContent = (sel) => {
    if (!sel || sel.rangeCount === 0) {
      return false;
    }

    const range = sel.getRangeAt(0);

    const isInside = (node) => {
      while (node) {
        if (node === contentRoot) {
          return true;
        }

        node = node.parentNode;
      }

      return false;
    };

    return isInside(range.startContainer) && isInside(range.endContainer);
  };

  // ---------------------------------------------------------------
  // 9. Clone current native selection
  // ---------------------------------------------------------------

  const cloneCurrentSelectionRange = () => {
    const sel = window.getSelection();

    if (!sel || sel.rangeCount === 0) {
      return null;
    }

    if (!isSelectionWithinContent(sel)) {
      return null;
    }

    const range = sel.getRangeAt(0);

    if (range.collapsed || !range.toString().trim()) {
      return null;
    }

    return range.cloneRange();
  };

  // ---------------------------------------------------------------
  // 10. Selection data
  // ---------------------------------------------------------------

  const getSelectionData = (range) => {
    if (!range) return null;

    const rawText = range.toString();

    const query = rawText.trim();

    if (!query) {
      return null;
    }

    const { start: rawStart, end: rawEnd } = computeOffsets(range);

    const leading = rawText.length - rawText.trimStart().length;

    const trailing = rawText.length - rawText.trimEnd().length;

    const start = rawStart + leading;

    const end = rawEnd - trailing;

    if (end <= start) {
      return null;
    }

    return {
      query,
      start,
      end,
    };
  };

  // ---------------------------------------------------------------
  // 11. Highlight class
  // ---------------------------------------------------------------

  const getHighlightClassName = (occ) => {
    const simp = !!occ.simplified;
    const tech = !!occ.technical;

    if (simp && tech) {
      return "highlight-marked highlight-marked--both";
    }

    if (simp) {
      return "highlight-marked highlight-marked--simplified";
    }

    if (tech) {
      return "highlight-marked highlight-marked--technical";
    }

    return "highlight-marked";
  };

  const buildAnswerText = (occ) => {
    const parts = [];

    if (occ.simplifiedAnswer) {
      parts.push(`Simplified:\n${occ.simplifiedAnswer}`);
    }

    if (occ.technicalAnswer) {
      parts.push(`Technical:\n${occ.technicalAnswer}`);
    }

    if (occ.note) {
      parts.push(`Annotation:\n${occ.note}`);
    }

    return parts.join("\n\n");
  };

  // ---------------------------------------------------------------
  // 12. Messages
  // ---------------------------------------------------------------

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

      setTimeout(() => {
        msg.remove();
      }, 500);
    }, 1500);
  };

  // ---------------------------------------------------------------
  // 13. History
  // ---------------------------------------------------------------

  const toggleHistoryPopover = () => {
    if (!historyPopover || !historyToggle) {
      return;
    }

    const next = historyPopover.hidden;

    historyPopover.hidden = !next;

    historyToggle.setAttribute("aria-expanded", String(!next));
  };

  const closeHistoryPopover = () => {
    if (!historyPopover || !historyToggle) {
      return;
    }

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

      if (historyCount) {
        historyCount.textContent = "0 items";
      }

      return;
    }

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
      if (!existing.levels.includes(level)) {
        existing.levels.push(level);
      }
    } else {
      historyEntries.push({
        text: clean,
        start,
        end,
        levels: [level],
      });
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

    matches[0].scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    closeHistoryPopover();

    historyFocusTimer = setTimeout(clearHistoryFocus, 2200);
  };

  // ---------------------------------------------------------------
  // 14. Occurrence structures
  // ---------------------------------------------------------------

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

  // ---------------------------------------------------------------
  // 15. Highlight event attachment
  // ---------------------------------------------------------------

  const showTooltip = (span) => {
    const query = span.dataset.highlightQuery;

    const start = Number(span.dataset.start);

    const end = Number(span.dataset.end);

    if (!query) return;

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
      <button
        class="tooltip-tab ${defaultTab === "ai" ? "tooltip-tab--active" : ""}"
        data-target="ai"
      >
        AI Answers
      </button>

      <button
        class="tooltip-tab ${
          defaultTab === "annotation" ? "tooltip-tab--active" : ""
        }"
        data-target="annotation"
      >
        Annotations
      </button>
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

    header.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-target]");

      if (!btn) return;

      header
        .querySelectorAll(".tooltip-tab")
        .forEach((t) => t.classList.toggle("tooltip-tab--active", t === btn));

      renderSection(btn.dataset.target);
    });

    tip.addEventListener("mousedown", (e) => e.stopPropagation());

    tip.addEventListener("touchstart", (e) => e.stopPropagation());

    document.body.appendChild(tip);

    activeTooltip = tip;

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

  const attachHighlightEvents = (span, query) => {
    if (span.dataset.clickBound === "true") {
      return;
    }

    span.addEventListener("click", (e) => {
      e.stopPropagation();

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

  // ---------------------------------------------------------------
  // 16. Apply stored occurrences
  // ---------------------------------------------------------------

  const applyOccurrences = (occs) => {
    if (!occs.length) return;

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

        if (localEnd <= localStart) {
          return;
        }

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

          span.textContent = selectedText;

          attachHighlightEvents(span, occ.queryOrig);

          fragment.appendChild(span);
        }

        cursor = localEnd;
      });

      if (cursor < txt.length) {
        fragment.appendChild(document.createTextNode(txt.slice(cursor)));
      }

      tn.parentNode.replaceChild(fragment, tn);

      globalOffset = nodeEnd;
    });
  };

  // ---------------------------------------------------------------
  // 17. Refresh highlights
  // ---------------------------------------------------------------

  const refreshAllHighlightsImpl = () => {
    contentRoot.innerHTML = _originalHtml;

    const occs = Array.from(occurrences.values());

    applyOccurrences(occs);

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

        if (!grouped.has(key)) {
          grouped.set(key, []);
        }

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
          if (i === 0) {
            s.classList.add("highlight-fragment-first");
          } else if (i === spans.length - 1) {
            s.classList.add("highlight-fragment-last");
          } else {
            s.classList.add("highlight-fragment-middle");
          }
        });
      }
    });
  };

  const _refreshAllHighlights = () => {
    refreshAllHighlightsImpl();
  };

  // ---------------------------------------------------------------
  // 18. Tooltip
  // ---------------------------------------------------------------

  let activeTooltip = null;

  const removeTooltip = () => {
    if (activeTooltip) {
      activeTooltip.remove();
      activeTooltip = null;
    }
  };

  // ---------------------------------------------------------------
  // 19. AI request
  // ---------------------------------------------------------------

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

    if (!resp.ok) {
      throw new Error(data?.error ?? `AI request failed (${resp.status})`);
    }

    if (!data.answer) {
      throw new Error("The AI did not return an explanation.");
    }

    setOccurrenceAnswer(query, start, end, level, data.answer);

    return data;
  };

  // ---------------------------------------------------------------
  // 20. AI section
  // ---------------------------------------------------------------

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

          <div class="ai-answer-content">
            ${renderMarkdown(storedAns)}
          </div>
        `;
      } else {
        const btn = document.createElement("button");

        btn.className = "ai-get-level";

        btn.textContent = `Get ${lvlCap} answer`;

        btn.addEventListener("click", async () => {
          const requestKey = `${normalise(query)}|${start}-${end}|${lvl}`;

          if (pendingAiRequests.has(requestKey)) {
            return;
          }

          pendingAiRequests.add(requestKey);

          btn.disabled = true;

          const old = btn.textContent;

          btn.textContent = "Thinking…";

          try {
            const data = await fetchAiAnswer(query, lvl, start, end);

            if (data && data.answer) {
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

  // ---------------------------------------------------------------
  // 21. Annotation section
  // ---------------------------------------------------------------

  const renderAnnotationSection = (query, start, end, container) => {
    const occ = getOrCreateOccurrence(query, start, end);

    const wrapper = document.createElement("div");

    wrapper.className = "annotation-edit";

    const existing = occ.note.replace(/</g, "&lt;");

    wrapper.innerHTML = `
      <textarea
        rows="3"
        class="annotation-textarea"
      >${existing}</textarea>

      <button class="annotation-save">
        Save
      </button>
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

        if (!resp.ok) {
          throw new Error(data.error ?? "Failed");
        }

        setOccurrenceAnnotation(query, start, end, data.note ?? note);

        textarea.classList.add("annotation-saved");

        setTimeout(() => {
          textarea.classList.remove("annotation-saved");
        }, 600);
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

  // ---------------------------------------------------------------
  // 22. Choice widget
  // ---------------------------------------------------------------

  const createChoiceWidget = (initialRange) => {
    /*
     * Always snapshot the selection when the widget is created.
     */
    latestSelectionRange =
      cloneCurrentSelectionRange() || initialRange.cloneRange();

    const choice = document.createElement("div");

    choice.className = "highlight-choice";

    choice.innerHTML = `
      <p class="highlight-choice__text">
        What would you like to do?
      </p>

      <button class="choice-ask-ai">
        Ask AI
      </button>

      <button class="choice-annotate">
        Add annotation
      </button>
    `;

    document.body.appendChild(choice);

    choiceWidget = choice;

    /*
     * IMPORTANT MOBILE FIX:
     *
     * Do NOT clear the native selection on touchstart
     * when the touch occurs inside contentRoot.
     *
     * The user may be grabbing a native selection handle.
     *
     * The old implementation removed the choice and called
     * removeAllRanges(), which destroyed the multi-word
     * selection before the browser finished adjusting it.
     */
    const clickOutside = (e) => {
      if (!choice.isConnected) {
        document.removeEventListener("mousedown", clickOutside);

        document.removeEventListener("touchstart", clickOutside);

        return;
      }

      if (choice.contains(e.target)) {
        return;
      }

      /*
       * Never destroy an active native selection from a
       * touchstart inside the module content.
       *
       * This is specifically for mobile selection handles.
       */
      if (e.type === "touchstart" && contentRoot.contains(e.target)) {
        return;
      }

      choice.remove();

      document.removeEventListener("mousedown", clickOutside);

      document.removeEventListener("touchstart", clickOutside);

      if (choiceWidget === choice) {
        choiceWidget = null;
      }

      /*
       * Only clear selection when this is an actual
       * outside interaction, not selection manipulation.
       */
      if (e.type !== "touchstart" || !selectionInteractionActive) {
        window.getSelection().removeAllRanges();
      }
    };

    document.addEventListener("mousedown", clickOutside);

    document.addEventListener("touchstart", clickOutside);

    /*
     * Position using the initial selection.
     * This is only visual positioning.
     */
    const rect = initialRange.getBoundingClientRect();

    const top = rect.bottom + window.scrollY + 6;

    const left = Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - choice.offsetWidth - 8,
    );

    choice.style.top = `${top}px`;

    choice.style.left = `${Math.max(8, left)}px`;

    // -------------------------------------------------------------
    // Ask AI
    // -------------------------------------------------------------

    choice.querySelector(".choice-ask-ai").addEventListener("click", (e) => {
      e.stopPropagation();

      /*
       * Resolve the FINAL browser selection.
       *
       * This is the selection after the user has dragged
       * the native handles.
       */
      const finalRange =
        cloneCurrentSelectionRange() ||
        latestSelectionRange?.cloneRange() ||
        initialRange.cloneRange();

      latestSelectionRange = finalRange.cloneRange();

      choice.remove();

      document.removeEventListener("mousedown", clickOutside);

      document.removeEventListener("touchstart", clickOutside);

      if (choiceWidget === choice) {
        choiceWidget = null;
      }

      mini = createAIMiniWidget(finalRange);
    });

    // -------------------------------------------------------------
    // Annotation
    // -------------------------------------------------------------

    choice.querySelector(".choice-annotate").addEventListener("click", (e) => {
      e.stopPropagation();

      const finalRange =
        cloneCurrentSelectionRange() ||
        latestSelectionRange?.cloneRange() ||
        initialRange.cloneRange();

      latestSelectionRange = finalRange.cloneRange();

      choice.remove();

      document.removeEventListener("mousedown", clickOutside);

      document.removeEventListener("touchstart", clickOutside);

      if (choiceWidget === choice) {
        choiceWidget = null;
      }

      mini = createAnnotationWidget(finalRange);
    });

    return choice;
  };

  // ---------------------------------------------------------------
  // 23. AI mini widget
  // ---------------------------------------------------------------

  const createAIMiniWidget = (originalRange) => {
    mini = document.createElement("div");

    mini.className = "ai-mini";

    mini.innerHTML = `
      <select class="ai-level">
        <option value="simplified">
          Simplified
        </option>

        <option value="technical">
          Technical
        </option>
      </select>

      <button class="ai-get">
        Get answer
      </button>

      <div class="ai-answer hidden"></div>
    `;

    document.body.appendChild(mini);

    /*
     * Stop widget interactions from reaching
     * the selection handlers.
     */
    mini.addEventListener("mousedown", (e) => e.stopPropagation());

    mini.addEventListener("touchstart", (e) => e.stopPropagation());

    /*
     * Position using the selection that opened the widget.
     */
    const rect = originalRange.getBoundingClientRect();

    mini.style.top = `${rect.bottom + window.scrollY + 6}px`;

    mini.style.left = `${Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - mini.offsetWidth - 8,
    )}px`;

    const clickOutside = (e) => {
      if (!mini) return;

      if (mini.contains(e.target)) {
        return;
      }

      mini.remove();

      document.removeEventListener("mousedown", clickOutside);

      document.removeEventListener("touchstart", clickOutside);

      mini = null;

      window.getSelection().removeAllRanges();

      latestSelectionRange = null;
    };

    document.addEventListener("mousedown", clickOutside);

    document.addEventListener("touchstart", clickOutside);

    // -------------------------------------------------------------
    // Get answer
    // -------------------------------------------------------------

    const btn = mini.querySelector(".ai-get");

    const levelSelect = mini.querySelector(".ai-level");

    btn.addEventListener("click", async () => {
      const level = levelSelect.value;

      /*
       * FINAL selection resolution.
       *
       * cloneCurrentSelectionRange() is checked first because
       * the browser's native selection is the authoritative
       * source after handle dragging.
       */
      const finalRange =
        cloneCurrentSelectionRange() ||
        latestSelectionRange?.cloneRange() ||
        originalRange.cloneRange();

      const selData = getSelectionData(finalRange);

      if (!selData) {
        console.warn("[highlight_ai] No valid selection.");

        return;
      }

      const { query, start, end } = selData;

      console.log("[highlight_ai] Final AI selection:", {
        query,
        start,
        end,
      });

      btn.disabled = true;

      const old = btn.textContent;

      btn.textContent = "Thinking…";

      try {
        const data = await fetchAiAnswer(query, level, start, end);

        if (data && data.answer) {
          const answerContainer = mini.querySelector(".ai-answer");

          answerContainer.innerHTML = "";

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

        /*
         * Clear native selection only AFTER the AI request.
         */
        window.getSelection().removeAllRanges();

        latestSelectionRange = null;
      }
    });

    return mini;
  };

  // ---------------------------------------------------------------
  // 24. Annotation widget
  // ---------------------------------------------------------------

  const createAnnotationWidget = (originalRange) => {
    const ann = document.createElement("div");

    ann.className = "annotation-widget";

    document.body.appendChild(ann);

    ann.addEventListener("mousedown", (e) => e.stopPropagation());

    ann.addEventListener("touchstart", (e) => e.stopPropagation());

    const rect = originalRange.getBoundingClientRect();

    ann.style.top = `${rect.bottom + window.scrollY + 6}px`;

    ann.style.left = `${Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - ann.offsetWidth - 8,
    )}px`;

    /*
     * Use the final selection, not blindly the initial range.
     */
    const finalRange =
      cloneCurrentSelectionRange() ||
      latestSelectionRange?.cloneRange() ||
      originalRange.cloneRange();

    const selection = getSelectionData(finalRange);

    if (!selection) {
      ann.remove();

      return ann;
    }

    const { query, start, end } = selection;

    ann.dataset.startOffset = String(start);

    ann.dataset.endOffset = String(end);

    renderAnnotationSection(query, start, end, ann);

    const clickOutside = (e) => {
      if (!ann.isConnected) {
        document.removeEventListener("mousedown", clickOutside);

        document.removeEventListener("touchstart", clickOutside);

        return;
      }

      if (ann.contains(e.target)) {
        return;
      }

      ann.remove();

      document.removeEventListener("mousedown", clickOutside);

      document.removeEventListener("touchstart", clickOutside);

      window.getSelection().removeAllRanges();

      latestSelectionRange = null;
    };

    document.addEventListener("mousedown", clickOutside);

    document.addEventListener("touchstart", clickOutside);

    return ann;
  };

  // ---------------------------------------------------------------
  // 25. Markdown
  // ---------------------------------------------------------------

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
          `<span class="inline-image"><img src="${escapeHtml(
            s,
          )}" alt="${escapeHtml(a)}"></span>`,
      )
      .replace(
        /\[([^\]]+)\]\(([^)]+)\)/g,
        (_, l, h) =>
          `<a href="${escapeHtml(
            h,
          )}" target="_blank" rel="noopener noreferrer">${escapeHtml(l)}</a>`,
      )
      .replace(
        /\*\*([^\*]+)\*\*/g,
        (_, b) => `<strong>${escapeHtml(b)}</strong>`,
      )
      .replace(/\*([^\*]+)\*/g, (_, i) => `<em>${escapeHtml(i)}</em>`)
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
      if (!inTable || !tableRows.length) {
        return;
      }

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

        header.forEach((c) => {
          html += `<th>${inlineFormatting(c)}</th>`;
        });

        html += "</tr></thead><tbody>";

        body.forEach((r) => {
          html += "<tr>";

          r.forEach((c) => {
            html += `<td>${inlineFormatting(c)}</td>`;
          });

          html += "</tr>";
        });

        html += "</tbody></table>";
      } else {
        tableRows.forEach((r) => {
          html += `<p>${inlineFormatting(r)}</p>`;
        });
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

        html += `<blockquote>${inlineFormatting(
          t.replace(/^>\s?/, ""),
        )}</blockquote>`;

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
            `<div class="message-image"><img src="${escapeHtml(
              s,
            )}" alt="${escapeHtml(a)}"></div>`,
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

  // ---------------------------------------------------------------
  // 26. Render answer
  // ---------------------------------------------------------------

  const renderAnswer = (miniWidget, html, cached) => {
    const box = miniWidget.querySelector(".ai-answer");

    box.innerHTML = `
      ${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ""}

      <div class="ai-answer-content">
        ${renderMarkdown(html)}
      </div>
    `;

    box.classList.remove("hidden");
  };

  // ---------------------------------------------------------------
  // 27. Selection → choice widget
  // ---------------------------------------------------------------

  const onSelectionDone = (e) => {
    /*
     * Ignore UI interactions.
     */
    if (
      e.target.closest(".highlight-choice") ||
      e.target.closest(".ai-mini") ||
      e.target.closest(".annotation-widget") ||
      e.target.closest(".highlight-answer-tooltip")
    ) {
      return;
    }

    const sel = window.getSelection();

    /*
     * The browser selection is authoritative.
     */
    const hasSelection = sel && sel.rangeCount > 0 && sel.toString().trim();

    /*
     * Hide history when clicking outside.
     */
    if (
      historyPopover &&
      !historyPopover.hidden &&
      !historyPopover.contains(e.target) &&
      !historyToggle?.contains(e.target)
    ) {
      closeHistoryPopover();
    }

    /*
     * Do not react to toolbar/widget clicks.
     */
    if (toolbar.contains(e.target) || (mini && mini.contains(e.target))) {
      return;
    }

    /*
     * No selection.
     */
    if (!hasSelection || !isSelectionWithinContent(sel)) {
      if (mini) {
        mini.remove();
        mini = null;
      }

      if (choiceWidget) {
        choiceWidget.remove();
        choiceWidget = null;
      }

      toolbar.style.display = "none";

      /*
       * Only clear our stored selection if
       * there is genuinely no selection.
       */
      latestSelectionRange = null;

      return;
    }

    /*
     * Save the current browser selection.
     */
    const range = sel.getRangeAt(0).cloneRange();

    latestSelectionRange = range.cloneRange();

    toolbar.style.display = "none";

    /*
     * Remove previous widget.
     */
    if (mini) {
      mini.remove();
      mini = null;
    }

    if (choiceWidget) {
      choiceWidget.remove();
      choiceWidget = null;
    }

    /*
     * Open choice widget for the CURRENT
     * selection.
     */
    choiceWidget = createChoiceWidget(range);
  };

  // ---------------------------------------------------------------
  // 28. Preload existing data
  // ---------------------------------------------------------------

  const preloadExistingData = async () => {
    if (!hasValidId) return;

    try {
      const [answersResp, annResp] = await Promise.all([
        fetch(`${apiBase}${moduleId}/highlight/`),

        fetch(`${apiBase}${moduleId}/annotation/`),
      ]);

      // ---------------------------------------------------------
      // Cached answers
      // ---------------------------------------------------------

      if (answersResp.ok) {
        const data = await answersResp.json();

        (data.answers || []).forEach((item) => {
          const query = (item.query || "").trim();

          const start = item.start_offset;

          const end = item.end_offset;

          if (!query || start == null || end == null) {
            return;
          }

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

      // ---------------------------------------------------------
      // Saved annotations
      // ---------------------------------------------------------

      if (annResp.ok) {
        const annData = await annResp.json();

        (annData.annotations || []).forEach((a) => {
          const query = (a.query || "").trim();

          const start = a.start_offset;

          const end = a.end_offset;

          if (!query || start == null || end == null) {
            return;
          }

          setOccurrenceAnnotation(query, start, end, a.note);

          addHistoryEntry(query, "annotation", start, end);
        });
      }

      _refreshAllHighlights();
    } catch (e) {
      console.warn("Could not preload highlights/annotations:", e);
    }
  };

  // ---------------------------------------------------------------
  // 29. Initialise
  // ---------------------------------------------------------------

  preloadExistingData();

  updateHistoryUI();

  if (historyToggle) {
    historyToggle.addEventListener("click", (ev) => {
      ev.stopPropagation();

      toggleHistoryPopover();
    });
  }

  // ---------------------------------------------------------------
  // 30. Mouse / touch handling
  // ---------------------------------------------------------------

  /*
   * Desktop:
   * mouseup is sufficient.
   */
  document.addEventListener("mouseup", onSelectionDone);

  /*
   * Mobile:
   *
   * touchend is used only to detect the completed
   * selection. The actual selection state is maintained
   * by selectionchange.
   */
  document.addEventListener("touchend", (e) => {
    /*
     * Give the browser a chance to finish updating
     * its native selection before reading it.
     */
    requestAnimationFrame(() => {
      onSelectionDone(e);
    });
  });

  // ---------------------------------------------------------------
  // 31. Detect mobile selection-handle interaction
  // ---------------------------------------------------------------

  document.addEventListener(
    "touchstart",
    (e) => {
      /*
       * If the touch starts inside the content while a
       * selection exists, treat it as potentially related
       * to selection manipulation.
       */
      const sel = window.getSelection();

      if (
        sel &&
        sel.rangeCount > 0 &&
        sel.toString().trim() &&
        isSelectionWithinContent(sel)
      ) {
        selectionInteractionActive = true;

        return;
      }

      selectionInteractionActive = false;
    },
    true,
  );

  document.addEventListener(
    "touchend",
    () => {
      /*
       * Do not immediately clear this before
       * onSelectionDone has processed the final range.
       */
      requestAnimationFrame(() => {
        selectionInteractionActive = false;
      });
    },
    true,
  );

  // ---------------------------------------------------------------
  // 32. Native selectionchange
  // ---------------------------------------------------------------

  document.addEventListener("selectionchange", () => {
    const sel = window.getSelection();

    const validSelection =
      sel &&
      sel.rangeCount > 0 &&
      sel.toString().trim() &&
      isSelectionWithinContent(sel);

    /*
     * THIS IS THE IMPORTANT MOBILE FIX.
     *
     * Every time the user moves a native selection
     * handle, the browser updates window.getSelection().
     *
     * We immediately snapshot that new Range.
     */
    if (validSelection) {
      latestSelectionRange = sel.getRangeAt(0).cloneRange();

      return;
    }

    /*
     * Do NOT destroy a widget merely because the browser
     * temporarily reports an empty selection during
     * handle manipulation.
     */
    if (selectionInteractionActive) {
      return;
    }

    /*
     * If the selection genuinely collapsed,
     * clean up the UI.
     */
    if (!validSelection) {
      /*
       * If a choice widget exists, don't destroy it merely
       * because the browser briefly collapses selection.
       *
       * The next touchend will determine whether the
       * interaction really ended.
       */
      if (choiceWidget && choiceWidget.isConnected) {
        return;
      }

      if (mini) {
        mini.remove();
        mini = null;
      }

      toolbar.style.display = "none";

      latestSelectionRange = null;
    }
  });

  // ---------------------------------------------------------------
  // 33. Outside click handling
  // ---------------------------------------------------------------

  document.addEventListener("mousedown", (e) => {
    if (activeTooltip && !activeTooltip.contains(e.target)) {
      removeTooltip();
    }

    if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
      mini.remove();
      mini = null;
    }

    if (!toolbar.contains(e.target)) {
      toolbar.style.display = "none";
    }
  });

  /*
   * IMPORTANT:
   *
   * Do NOT duplicate the old destructive touchstart handler here.
   *
   * The previous handler was one of the causes of the
   * mobile selection-handle problem because it could call
   * mini.remove(), followed by removeAllRanges(), while
   * Android was still adjusting the selection.
   */

  // ---------------------------------------------------------------
  // 34. Return optional cleanup
  // ---------------------------------------------------------------

  return {
    destroy() {
      document.removeEventListener("mouseup", onSelectionDone);

      if (mini) {
        mini.remove();
        mini = null;
      }

      if (choiceWidget) {
        choiceWidget.remove();
        choiceWidget = null;
      }

      removeTooltip();

      latestSelectionRange = null;
    },
  };
}