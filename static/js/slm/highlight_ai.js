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
  //    to this clean copy and then re-apply **only the stored
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
   * 3️⃣ Normalise queries (lower-case) – DB stores lower-case
   * ----------------------------------------------------------------- */
  const normalise = (txt) => (txt || "").trim().toLowerCase();

  /* -----------------------------------------------------------------
   * 4️⃣ Internal storage – keyed by a *unique occurrence key*
   * ----------------------------------------------------------------- */
  const occurrenceKey = (q, s, e) => `${q}|${s}-${e}`; // q is lower-cased

  const occurrences = new Map();
  // key → {
  //     queryOrig,
  //     queryLC,
  //     start,
  //     end,
  //     simplified,
  //     technical,
  //     annotated,
  //     note,
  //     simplifiedAnswer,
  //     technicalAnswer
  // }

  /* -----------------------------------------------------------------
   * 5️⃣ Helpers – compute offsets and selection data
   * ----------------------------------------------------------------- */

  const computeOffsets = (range) => {
    /*
     * Calculate offsets against the clean text inside contentRoot.
     *
     * Using Range.toString() here also works when the selection
     * boundaries are element nodes rather than text nodes.
     */
    const tmp = document.createRange();

    // Start offset
    tmp.setStart(contentRoot, 0);
    tmp.setEnd(range.startContainer, range.startOffset);

    const start = tmp.toString().length;

    // End offset
    tmp.setEnd(range.endContainer, range.endOffset);

    const end = tmp.toString().length;

    return { start, end };
  };

  /*
   * Return the selected text together with offsets that exclude
   * accidental leading/trailing whitespace from the browser selection.
   *
   * This prevents whitespace-only highlight spans from appearing before
   * or after a phrase.
   */
  const getSelectionData = (range) => {
    const rawText = range.toString();
    const query = rawText.trim();

    if (!query) return null;

    const { start: rawStart, end: rawEnd } = computeOffsets(range);

    const leading = rawText.length - rawText.trimStart().length;

    const trailing = rawText.length - rawText.trimEnd().length;

    const start = rawStart + leading;
    const end = rawEnd - trailing;

    if (end <= start) return null;

    return {
      query,
      start,
      end,
    };
  };

  /* -----------------------------------------------------------------
   * 6️⃣ CSS class helper
   * ----------------------------------------------------------------- */
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

  /* -----------------------------------------------------------------
   * 7️⃣ UI helpers
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

      return;
    }

    // Newest first.
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
      window.clearTimeout(historyFocusTimer);
      historyFocusTimer = null;
    }

    contentRoot
      .querySelectorAll(".highlight-history-focused")
      .forEach((span) => {
        span.classList.remove("highlight-history-focused");
      });
  };

  const focusHighlight = (start, end) => {
    const selector = `.highlight-marked[data-start="${start}"][data-end="${end}"]`;

    const matches = Array.from(contentRoot.querySelectorAll(selector));

    if (!matches.length) return;

    clearHistoryFocus();

    matches.forEach((span) => {
      span.classList.add("highlight-history-focused");
    });

    const target = matches[0];

    target.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    closeHistoryPopover();

    historyFocusTimer = window.setTimeout(clearHistoryFocus, 2200);
  };

  /* -----------------------------------------------------------------
   * 8️⃣ Create / update occurrence data structures
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
   * 9️⃣ Apply stored occurrences without changing the original HTML
   *
   * IMPORTANT:
   * We do NOT use Range.extractContents().
   *
   * Instead, we:
   *   1. Collect the original text nodes.
   *   2. Calculate which part of each text node belongs to an
   *      occurrence.
   *   3. Replace only that text portion with a span.
   *
   * This preserves <p>, <li>, <strong>, <em>, <a>, <br>, etc.
   *
   * Therefore:
   *   - single-word selections still work;
   *   - phrases in one text node still use one span;
   *   - phrases crossing HTML elements use multiple spans;
   *   - all fragments still belong to the same occurrence because
   *     they share the same data-start/data-end.
   * ----------------------------------------------------------------- */

  const applyOccurrences = (occs) => {
    if (!occs.length) return;

    /*
     * Take all text nodes from the clean DOM before inserting
     * any highlight spans.
     */
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

    /*
     * Ignore invalid/empty occurrences and render them
     * in document order.
     */
    const validOccurrences = occs
      .filter(
        (occ) =>
          Number.isFinite(occ.start) &&
          Number.isFinite(occ.end) &&
          occ.end > occ.start,
      )
      .sort((a, b) => a.start - b.start || a.end - b.end);

    let globalOffset = 0;

    textNodes.forEach((textNode) => {
      const text = textNode.nodeValue || "";

      const nodeStart = globalOffset;

      const nodeEnd = nodeStart + text.length;

      /*
       * Find occurrences that touch this
       * particular text node.
       */
      const touching = validOccurrences.filter(
        (occ) => occ.start < nodeEnd && occ.end > nodeStart,
      );

      /*
       * Nothing to highlight in this node.
       */
      if (!touching.length || !textNode.parentNode) {
        globalOffset = nodeEnd;
        return;
      }

      const fragment = document.createDocumentFragment();

      let cursor = 0;

      touching.forEach((occ) => {
        /*
         * Convert the global occurrence offsets
         * into offsets relative to this text node.
         */
        let localStart = Math.max(0, occ.start - nodeStart);

        const localEnd = Math.min(text.length, occ.end - nodeStart);

        /*
         * Ignore invalid ranges.
         */
        if (
          localEnd <= 0 ||
          localStart >= text.length ||
          localEnd <= localStart
        ) {
          return;
        }

        /*
         * Prevent malformed overlapping occurrences
         * from creating nested spans.
         *
         * Normal user selections should never overlap.
         */
        localStart = Math.max(localStart, cursor);

        if (localEnd <= localStart) {
          return;
        }

        /*
         * Add normal text before the highlight.
         */
        if (localStart > cursor) {
          fragment.appendChild(
            document.createTextNode(text.slice(cursor, localStart)),
          );
        }

        /*
         * Add the highlighted portion.
         */
        const selectedText = text.slice(localStart, localEnd);

        if (selectedText.length) {
          const span = document.createElement("span");

          span.className = getHighlightClassName(occ);

          span.dataset.highlightQuery = occ.queryOrig;

          span.dataset.start = String(occ.start);

          span.dataset.end = String(occ.end);

          span.dataset.answer = buildAnswerText(occ);

          span.textContent = selectedText;

          attachHighlightEvents(span, occ.queryOrig);

          fragment.appendChild(span);
        }

        cursor = localEnd;
      });

      /*
       * Add the remaining normal text.
       */
      if (cursor < text.length) {
        fragment.appendChild(document.createTextNode(text.slice(cursor)));
      }

      /*
       * Replace ONLY this text node.
       *
       * The parent HTML element itself is untouched.
       */
      textNode.parentNode.replaceChild(fragment, textNode);

      globalOffset = nodeEnd;
    });
  };

  /* -----------------------------------------------------------------
   * 🔟 Refresh all highlights
   * ----------------------------------------------------------------- */

  const refreshAllHighlightsImpl = () => {
    /*
     * Always start from the untouched server-rendered HTML.
     */
    contentRoot.innerHTML = _originalHtml;

    /*
     * Rebuild all saved occurrences from
     * the original DOM.
     */
    const occs = Array.from(occurrences.values());

    applyOccurrences(occs);
  };

  /* -----------------------------------------------------------------
   * 11️⃣ Refresh wrapper
   * ----------------------------------------------------------------- */

  const _refreshAllHighlights = () => {
    refreshAllHighlightsImpl();
  };

  /* -----------------------------------------------------------------
   * 12️⃣ Tooltip handling
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

    const data = await resp.json();

    if (!data.cached && data.answer) {
      setOccurrenceAnswer(query, start, end, level, data.answer);
    }

    return data;
  };

  const renderAiSection = (query, start, end, container) => {
    const occ = getOrCreateOccurrence(query, start, end);

    const levels = ["simplified", "technical"];

    levels.forEach((lvl) => {
      const lvlCap = lvl.charAt(0).toUpperCase() + lvl.slice(1);

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
          btn.disabled = true;

          const old = btn.textContent;

          btn.textContent = "Thinking…";

          try {
            const data = await fetchAiAnswer(query, lvl, start, end);

            if (data && data.answer) {
              renderAiSection(query, start, end, container);
            } else {
              console.error("AI answer error:", data);
            }
          } finally {
            btn.textContent = old;

            btn.disabled = false;
          }
        });

        wrapper.appendChild(btn);
      }

      container.appendChild(wrapper);
    });
  };

  const renderAnnotationSection = (query, start, end, container) => {
    const occ = getOrCreateOccurrence(query, start, end);

    const existing = occ.note || "";

    const wrapper = document.createElement("div");

    wrapper.className = "annotation-edit";

    wrapper.innerHTML = `
            <textarea rows="3" class="annotation-textarea">${existing.replace(
              /</g,
              "&lt;",
            )}</textarea>
            <button class="annotation-save">Save</button>
        `;

    const saveBtn = wrapper.querySelector(".annotation-save");

    const textarea = wrapper.querySelector(".annotation-textarea");

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
          throw new Error(data.error || "Failed");
        }

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

  const showTooltip = (span) => {
    const query = span.dataset.highlightQuery;

    const start = Number(span.dataset.start);

    const end = Number(span.dataset.end);

    if (!query) return;

    /*
     * Clicking another fragment of the same
     * logical occurrence toggles the tooltip.
     */
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
            <button class="tooltip-tab ${
              defaultTab === "ai" ? "tooltip-tab--active" : ""
            }" data-target="ai">AI Answers</button>

            <button class="tooltip-tab ${
              defaultTab === "annotation" ? "tooltip-tab--active" : ""
            }" data-target="annotation">Annotations</button>
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

    document.body.appendChild(tip);

    /*
     * Position the tooltip against the
     * actual fragment that was clicked.
     */
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

    activeTooltip = tip;
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

  /* -----------------------------------------------------------------
   * 13️⃣ UI: Choice widget
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

    const rect = range.getBoundingClientRect();

    const top = rect.bottom + window.scrollY + 6;

    const left = Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - choice.offsetWidth - 8,
    );

    choice.style.top = `${top}px`;

    choice.style.left = `${left}px`;

    const clickOutside = (e) => {
      if (!choice.contains(e.target)) {
        choice.remove();

        document.removeEventListener("mousedown", clickOutside);

        mini = null;
      }
    };

    document.addEventListener("mousedown", clickOutside);

    choice.querySelector(".choice-ask-ai").addEventListener("click", () => {
      choice.remove();

      document.removeEventListener("mousedown", clickOutside);

      mini = createAIMiniWidget(range);
    });

    choice.querySelector(".choice-annotate").addEventListener("click", () => {
      choice.remove();

      document.removeEventListener("mousedown", clickOutside);

      mini = createAnnotationWidget(range);
    });

    return choice;
  };

  /* -----------------------------------------------------------------
   * 14️⃣ Mini-AI widget
   * ----------------------------------------------------------------- */

  const createAIMiniWidget = (range) => {
    const miniWidget = document.createElement("div");

    miniWidget.className = "ai-mini";

    miniWidget.innerHTML = `
            <select class="ai-level">
                <option value="simplified">Simplified</option>
                <option value="technical">Technical</option>
            </select>

            <button class="ai-get">Get answer</button>

            <div class="ai-answer hidden"></div>
        `;

    document.body.appendChild(miniWidget);

    const rect = range.getBoundingClientRect();

    const top = rect.bottom + window.scrollY + 6;

    const left = Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - miniWidget.offsetWidth - 8,
    );

    miniWidget.style.top = `${top}px`;

    miniWidget.style.left = `${left}px`;

    const clickOutside = (e) => {
      if (!miniWidget.contains(e.target)) {
        miniWidget.remove();

        document.removeEventListener("mousedown", clickOutside);
      }
    };

    document.addEventListener("mousedown", clickOutside);

    const btn = miniWidget.querySelector(".ai-get");

    const levelSelect = miniWidget.querySelector(".ai-level");

    btn.addEventListener("click", () => {
      const lvl = levelSelect.value;

      performAIQuery(range, lvl, miniWidget);
    });

    return miniWidget;
  };

  /* -----------------------------------------------------------------
   * 15️⃣ Perform the AI request
   * ----------------------------------------------------------------- */

  const performAIQuery = async (range, level, miniWidget) => {
    /*
     * Use the original Range instead of window.getSelection().
     *
     * This is important because the selection can change while
     * the mini widget is open.
     */
    const selection = getSelectionData(range);

    if (!selection) return;

    const { query, start, end } = selection;

    const btn = miniWidget.querySelector(".ai-get");

    if (!btn) return;

    const old = btn.textContent;

    btn.textContent = "Thinking…";

    btn.disabled = true;

    try {
      const resp = await fetch(`${apiBase}${moduleId}/highlight/`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify({
          query,
          level,
          start_offset: start,
          end_offset: end,
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const data = await resp.json();

      if (data && data.answer) {
        setOccurrenceAnswer(query, start, end, level, data.answer);

        addHistoryEntry(query, level, start, end);
      }
    } catch (err) {
      console.error("AI request failed:", err);

      renderAnswer(
        miniWidget,
        "<em>Sorry – the AI service could not be reached.</em>",
        false,
      );
    } finally {
      btn.textContent = old;

      btn.disabled = false;
    }
  };

  /* -----------------------------------------------------------------
   * 16️⃣ Annotation widget
   * ----------------------------------------------------------------- */

  const createAnnotationWidget = (range) => {
    const ann = document.createElement("div");

    ann.className = "annotation-widget";

    document.body.appendChild(ann);

    const rect = range.getBoundingClientRect();

    const top = rect.bottom + window.scrollY + 6;

    const left = Math.min(
      rect.left + window.scrollX,
      document.documentElement.clientWidth - ann.offsetWidth - 8,
    );

    ann.style.top = `${top}px`;

    ann.style.left = `${left}px`;

    /*
     * Compute the exact selected text and offsets once.
     */
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
      if (!ann.contains(e.target)) {
        ann.remove();

        document.removeEventListener("mousedown", clickOutside);

        mini = null;
      }
    };

    document.addEventListener("mousedown", clickOutside);

    return ann;
  };

  /* -----------------------------------------------------------------
   * 17️⃣ Markdown → HTML
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

  /* -----------------------------------------------------------------
   * 18️⃣ Bind selection → choice widget
   * ----------------------------------------------------------------- */

  let mini = null;

  const isSelectionWithinContent = (sel) => {
    if (!sel || sel.rangeCount === 0) {
      return false;
    }

    const range = sel.getRangeAt(0);

    const up = (node) => {
      while (node) {
        if (node === contentRoot) {
          return true;
        }

        node = node.parentNode;
      }

      return false;
    };

    return up(range.startContainer) && up(range.endContainer);
  };

  const onSelectionDone = (e) => {
    const sel = window.getSelection();

    const txt = sel.toString().trim();

    // Close history popover if click is outside it.
    if (
      historyPopover &&
      !historyPopover.hidden &&
      !historyPopover.contains(e.target) &&
      !historyToggle?.contains(e.target)
    ) {
      closeHistoryPopover();
    }

    // Ignore clicks inside the toolbar
    // or an already-open widget.
    if (toolbar.contains(e.target) || (mini && mini.contains(e.target))) {
      return;
    }

    if (!txt || !isSelectionWithinContent(sel)) {
      if (mini) {
        mini.remove();
      }

      mini = null;

      toolbar.style.display = "none";

      return;
    }

    toolbar.style.display = "none";

    const range = sel.getRangeAt(0);

    if (mini) {
      mini.remove();
    }

    mini = createChoiceWidget(range);
  };

  /* -----------------------------------------------------------------
   * 19️⃣ Pre-load cached highlights & annotations
   * ----------------------------------------------------------------- */

  const preloadExistingData = async () => {
    if (!hasValidId) {
      return;
    }

    try {
      const [answersResp, annResp] = await Promise.all([
        fetch(`${apiBase}${moduleId}/highlight/`),
        fetch(`${apiBase}${moduleId}/annotation/`),
      ]);

      // ----- cached answers -----
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

      // ----- saved annotations -----
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

      // ----- finally rebuild UI -----
      _refreshAllHighlights();
    } catch (e) {
      console.warn("Could not preload highlights/annotations:", e);
    }
  };

  /* -----------------------------------------------------------------
   * Initialise everything
   * ----------------------------------------------------------------- */

  preloadExistingData();

  updateHistoryUI();

  if (historyToggle) {
    historyToggle.addEventListener("click", (ev) => {
      ev.stopPropagation();

      toggleHistoryPopover();
    });
  }

  /* -----------------------------------------------------------------
   * Mouse / touch handling
   * ----------------------------------------------------------------- */

  document.addEventListener("mouseup", onSelectionDone);

  document.addEventListener("touchend", (e) =>
    setTimeout(() => onSelectionDone(e), 10),
  );

  document.addEventListener("selectionchange", () => {
    const sel = window.getSelection();

    const hasSelection =
      sel && sel.toString().trim() && isSelectionWithinContent(sel);

    const keepOpen = mini && mini.classList.contains("annotation-widget");

    if (!hasSelection && !keepOpen) {
      if (mini) {
        mini.remove();
      }

      mini = null;

      toolbar.style.display = "none";
    }
  });

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

  document.addEventListener("touchstart", (e) => {
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
}
