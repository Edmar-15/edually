// static/js/slm/highlight_ai.js
// ---------------------------------------------------------------
// Highlight → Ask‑AI widget (works for Modules *and* PersonalMaterials)
// ---------------------------------------------------------------
import { csrftoken } from "./utils.js";

/**
 * Initialise the Highlight‑→‑Ask‑AI behaviour.
 *
 * @param {HTMLElement} toolbar        – the floating toolbar that already exists
 *                                      (it will be hidden after a selection).
 * @param {number|null} moduleId      – PK of the current object (Module or
 *                                      PersonalMaterial).  Pass `null` if the
 *                                      page does **not** have a highlight API.
 * @param {HTMLElement|string} contentScope – selector or element that should
 *                                            accept highlighting.
 * @param {string} apiBase           – base URL for the highlight API.
 *                                      Defaults to the original “modules” endpoint.
 *                                      Example for personal material:
 *                                      '/slm/api/personal-materials/'
 */
export function initHighlightAI(
    toolbar,
    moduleId,
    contentScope = ".module-content-card .module-content",
    apiBase = "/slm/api/modules/"
) {
    /* -----------------------------------------------------------------
     * 0️⃣ Abort early if we have no id or no API base (e.g. static pages)
     * ----------------------------------------------------------------- */
    const hasValidId = Number.isInteger(moduleId) && moduleId > 0;
    if (!hasValidId) {
        // The rest of the UI (selection toolbar, mini‑AI widget) still works,
        // but we will skip any network calls that would 404.
        console.info(
            "[highlight_ai] No valid id supplied – highlight cache disabled."
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

    /* -----------------------------------------------------------------
     * 2️⃣ History UI elements
     * ----------------------------------------------------------------- */
    const historyList = document.getElementById("highlight-history-list");
    const historyCount = document.getElementById("highlight-history-count");
    const historyToggle = document.getElementById("highlight-history-toggle");
    const historyPopover = document.getElementById(
        "highlight-history-popover"
    );

    const historyEntries = [];
    let historyFocusTimer = null;

    // Reset any stale UI when the script initialises on a new page.
    if (historyList) historyList.innerHTML = "";
    if (historyCount) historyCount.textContent = "0 items";

    /* -----------------------------------------------------------------
     * 3️⃣ Normalise queries (lower‑case) – DB stores lower‑case
     * ----------------------------------------------------------------- */
    const normalise = (txt) => (txt || "").trim().toLowerCase();

    // Internal maps keyed by the *normalised* query.
    const highlightStates = new Map(); // { simplified:bool, technical:bool }
    const answerStore = new Map(); // { simplified:'html', technical:'html' }

    /* -----------------------------------------------------------------
     * 4️⃣ History UI helpers
     * ----------------------------------------------------------------- */
    const toggleHistoryPopover = () => {
        if (!historyPopover || !historyToggle) return;
        const next = historyPopover.hidden;
        historyPopover.hidden = !next;
        historyToggle.setAttribute("aria-expanded", String(next));
    };
    const closeHistoryPopover = () => {
        if (!historyPopover || !historyToggle) return;
        historyPopover.hidden = true;
        historyToggle.setAttribute("aria-expanded", "false");
    };
    const updateHistoryUI = () => {
        if (!historyList) return;
        historyList.innerHTML = "";
        if (historyEntries.length === 0) {
            const empty = document.createElement("li");
            empty.className = "module-content-history__item";
            empty.textContent = "No highlights yet.";
            historyList.appendChild(empty);
        } else {
            historyEntries.slice().reverse().forEach((entry) => {
                const li = document.createElement("li");
                li.className = "module-content-history__item";
                li.tabIndex = 0;
                li.innerHTML = `
                    <span class="module-content-history__text">${entry.text}</span>
                    <span class="module-content-history__meta">${entry.levels.join(
                        " + "
                    )}</span>
                `;
                li.addEventListener("click", () =>
                    focusHighlightByQuery(entry.text)
                );
                li.addEventListener("keydown", (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        focusHighlightByQuery(entry.text);
                    }
                });
                historyList.appendChild(li);
            });
        }
        if (historyCount) {
            historyCount.textContent = `${historyEntries.length} ${
                historyEntries.length === 1 ? "item" : "items"
            }`;
        }
    };
    const addHistoryEntry = (text, level) => {
        const clean = (text || "").trim();
        if (!clean) return;
        const existing = historyEntries.find((e) => e.text === clean);
        if (existing) {
            if (!existing.levels.includes(level)) existing.levels.push(level);
        } else {
            historyEntries.push({ text: clean, levels: [level] });
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
            .forEach((span) => span.classList.remove("highlight-history-focused"));
    };

    const focusHighlightByQuery = (query) => {
        const q = normalise(query);
        if (!q) return;

        const matches = Array.from(
            contentRoot.querySelectorAll(
                ".highlight-marked[data-highlight-query]"
            )
        ).filter(
            (span) => normalise(span.dataset.highlightQuery) === q
        );

        if (!matches.length) return;

        clearHistoryFocus();
        matches.forEach((span) => span.classList.add("highlight-history-focused"));

        const target = matches[0];
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        closeHistoryPopover();

        historyFocusTimer = window.setTimeout(() => {
            clearHistoryFocus();
        }, 2200);
    };

    /* -----------------------------------------------------------------
     * 5️⃣ Highlight state / answer storage
     * ----------------------------------------------------------------- */
    const setHighlightState = (query, level) => {
        const q = normalise(query);
        if (!q) return;
        const cur = highlightStates.get(q) || { simplified: false, technical: false };
        cur[level] = true;
        highlightStates.set(q, cur);
    };
    const setHighlightAnswer = (query, level, answer) => {
        const q = normalise(query);
        if (!q) return;
        const cur = answerStore.get(q) || {};
        cur[level] = answer;
        answerStore.set(q, cur);
        setHighlightState(q, level);
    };
    const buildAnswerText = (query) => {
        const q = normalise(query);
        if (!q) return "";
        const ans = answerStore.get(q) || {};
        const parts = [];
        if (ans.simplified) parts.push(`Simplified:\n${ans.simplified}`);
        if (ans.technical) parts.push(`Technical:\n${ans.technical}`);
        return parts.join("\n\n");
    };

    /* -----------------------------------------------------------------
     * 6️⃣ CSS class helper
     * ----------------------------------------------------------------- */
    const getHighlightClassName = (state) => {
        const simp = !!state?.simplified;
        const tech = !!state?.technical;
        if (simp && tech) return "highlight-marked highlight-marked--both";
        if (simp) return "highlight-marked highlight-marked--simplified";
        if (tech) return "highlight-marked highlight-marked--technical";
        return "highlight-marked";
    };

    /* -----------------------------------------------------------------
     * 7️⃣ Tooltip handling (click‑to‑show)
     * ----------------------------------------------------------------- */
    let activeTooltip = null; // only one tooltip at a time

    const removeTooltip = () => {
        if (activeTooltip) {
            activeTooltip.remove();
            activeTooltip = null;
        }
    };

    const showTooltip = (span, query) => {
        const answer = buildAnswerText(query);
        if (!answer) return;

        if (activeTooltip && activeTooltip.dataset.for === query) {
            removeTooltip();
            return;
        }

        removeTooltip();

        const tip = document.createElement("div");
        tip.className = "highlight-answer-tooltip";
        tip.dataset.for = query;
        tip.innerHTML = `<div class="highlight-answer-tooltip__body">${renderMarkdown(
            answer
        )}</div>`;
        document.body.appendChild(tip);

        const rect = span.getBoundingClientRect();
        const maxW = Math.min(320, window.innerWidth - 24);
        const left = Math.min(
            rect.left + window.scrollX,
            document.documentElement.clientWidth - maxW - 8
        );
        const top = rect.bottom + window.scrollY + 8;

        tip.style.top = `${top}px`;
        tip.style.left = `${Math.max(8, left)}px`;
        tip.style.maxWidth = `${maxW}px`;
        activeTooltip = tip;
    };

    const attachHighlightEvents = (span, query) => {
        if (span.dataset.clickBound === "true") return;

        span.addEventListener("click", (e) => {
            e.stopPropagation();
            showTooltip(span, query);
        });

        span.setAttribute("tabindex", "0");
        span.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                showTooltip(span, query);
            }
        });

        span.dataset.clickBound = "true";
    };

    /* -----------------------------------------------------------------
     * 8️⃣ Keep existing spans in sync with internal maps
     * ----------------------------------------------------------------- */
    const syncHighlightSpans = () => {
        if (!contentRoot) return;
        const spans = Array.from(
            contentRoot.querySelectorAll(".highlight-marked")
        );
        spans.forEach((span) => {
            const query =
                span.dataset.highlightQuery ||
                span.textContent?.trim().toLowerCase() ||
                "";
            if (!query) return;
            const state = highlightStates.get(query) || {
                simplified: false,
                technical: false,
            };
            span.className = getHighlightClassName(state);
            span.dataset.answer = buildAnswerText(query);
            attachHighlightEvents(span, query);
        });
    };

    /* -----------------------------------------------------------------
     * 9️⃣ Apply a highlight to *all* occurrences of a query
     * ----------------------------------------------------------------- */
    const applyHighlightToQuery = (query, state) => {
        const q = normalise(query);
        if (!q) return;

        const className = getHighlightClassName(state);
        const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const regex = new RegExp(`(${escaped})`, "gi"); // case‑insensitive

        const walker = document.createTreeWalker(contentRoot, NodeFilter.SHOW_TEXT, {
            acceptNode: (node) => {
                if (!node.nodeValue) return NodeFilter.FILTER_REJECT;
                if (!node.nodeValue.toLowerCase().includes(q)) return NodeFilter.FILTER_REJECT;
                if (
                    node.parentNode &&
                    node.parentNode.closest &&
                    node.parentNode.closest(".highlight-marked")
                ) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            },
        });

        const textNodes = [];
        let cur = walker.nextNode();
        while (cur) {
            textNodes.push(cur);
            cur = walker.nextNode();
        }

        textNodes.forEach((textNode) => {
            const txt = textNode.nodeValue || "";
            if (!regex.test(txt)) return;
            regex.lastIndex = 0;
            const frag = document.createDocumentFragment();
            let last = 0;
            let match;
            while ((match = regex.exec(txt)) !== null) {
                if (match.index > last) {
                    frag.appendChild(
                        document.createTextNode(txt.slice(last, match.index))
                    );
                }
                const span = document.createElement("span");
                span.className = className;
                span.dataset.highlightQuery = q;
                span.dataset.answer = buildAnswerText(q);
                span.appendChild(document.createTextNode(match[1])); // keep original casing
                attachHighlightEvents(span, q);
                frag.appendChild(span);
                last = match.index + match[1].length;
            }
            if (last < txt.length) {
                frag.appendChild(document.createTextNode(txt.slice(last)));
            }
            if (frag.childNodes.length) {
                textNode.parentNode.replaceChild(frag, textNode);
            }
        });

        syncHighlightSpans();
    };

    /* -----------------------------------------------------------------
     * 🔟 Mini‑AI widget (the small box that appears after a selection)
     * ----------------------------------------------------------------- */
    const createMiniAI = (range) => {
        const mini = document.createElement("div");
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
        const rect = range.getBoundingClientRect();
        const top = rect.bottom + window.scrollY + 6;
        const left = Math.min(
            rect.left + window.scrollX,
            document.documentElement.clientWidth - mini.offsetWidth - 8
        );
        mini.style.top = `${top}px`;
        mini.style.left = `${left}px`;

        const clickOutside = (e) => {
            if (!mini.contains(e.target)) {
                mini.remove();
                document.removeEventListener("mousedown", clickOutside);
            }
        };
        document.addEventListener("mousedown", clickOutside);
        return mini;
    };

    /* -----------------------------------------------------------------
     * 11️⃣ Markdown → HTML (tiny renderer – no external libs)
     * ----------------------------------------------------------------- */
    const escapeHtml = (v) =>
        v.replace(/&/g, "&amp;")
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
                        s
                    )}" alt="${escapeHtml(a)}"></span>`
            )
            .replace(
                /\[([^\]]+)\]\(([^)]+)\)/g,
                (_, l, h) =>
                    `<a href="${escapeHtml(h)}" target="_blank" rel="noopener noreferrer">${escapeHtml(
                        l
                    )}</a>`
            )
            .replace(/\*\*([^*]+)\*\*/g, (_, b) => `<strong>${escapeHtml(b)}</strong>`)
            .replace(/\*([^*]+)\*/g, (_, i) => `<em>${escapeHtml(i)}</em>`)
            .replace(/`([^`]+)`/g, (_, c) => `<code>${escapeHtml(c)}</code>`);

    const renderMarkdown = (txt) => {
        if (!txt) return "";
        const lines = escapeHtml(txt).split(/\r?\n/);
        let html = "",
            listType = null,
            listOpen = false,
            tableRows = [],
            inTable = false;

        const closeList = () => {
            if (listOpen) {
                html += listType === "ol" ? "</ol>" : "</ul>";
                listOpen = false;
                listType = null;
            }
        };
        const flushTable = () => {
            if (!inTable || tableRows.length === 0) return;
            const rows = tableRows
                .map((r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim()))
                .filter((r) => r.length);
            const header = rows[0] || [],
                sep = rows[1] || [],
                body = rows.slice(2);
            const isTable = sep.every((c) => /^:?-+:?$/.test(c));

            if (isTable) {
                html += "<table class=\"message-table\"><thead><tr>";
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
                html += "<hr class=\"message-hr\"/>";
                continue;
            }
            if (/^>\s?/.test(t)) {
                closeList();
                flushTable();
                html += `<blockquote>${inlineFormatting(
                    t.replace(/^>\s?/, "")
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
                            s
                        )}" alt="${escapeHtml(a)}"></div>`
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

    const renderAnswer = (mini, html, cached) => {
        const box = mini.querySelector(".ai-answer");
        box.innerHTML = `
            ${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ""}
            <div class="ai-answer-content">${renderMarkdown(html)}</div>
        `;
        box.classList.remove("hidden");
    };

    /* -----------------------------------------------------------------
     * 12️⃣ Ask the AI (POST)
     * ----------------------------------------------------------------- */
    const askAI = async (range, level) => {
        const sel = window.getSelection();
        const query = sel.toString().trim();
        if (!query) return;

        const mini = createMiniAI(range);
        const btn = mini.querySelector(".ai-get");
        const old = btn.textContent;
        btn.textContent = "Thinking…";
        btn.disabled = true;

        try {
            const resp = await fetch(
                `${apiBase}${moduleId}/highlight/`,
                {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrftoken,
                    },
                    body: JSON.stringify({ query, level }),
                }
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json(); // {answer:"<html>", cached:true|false}
            renderAnswer(mini, data.answer, !!data.cached);
            setHighlightAnswer(query, level, data.answer);
            markSelection(range, level);
            syncHighlightSpans();
            addHistoryEntry(query, level);
        } catch (err) {
            console.error("AI request failed:", err);
            renderAnswer(
                mini,
                "<em>Sorry – the AI service could not be reached.</em>",
                false
            );
        } finally {
            btn.textContent = old;
            btn.disabled = false;
        }
    };

    /* -----------------------------------------------------------------
     * 13️⃣ Visual marking of the selected fragment
     * ----------------------------------------------------------------- */
    const markSelection = (range, level) => {
        const selected = range.toString().trim();
        if (!selected) return;
        const q = normalise(selected);
        const span = document.createElement("span");
        span.className = getHighlightClassName({
            simplified: level === "simplified",
            technical: level === "technical",
        });
        span.dataset.highlightQuery = q;
        span.dataset.answer = buildAnswerText(q);
        span.appendChild(range.extractContents());
        attachHighlightEvents(span, q);
        range.insertNode(span);
    };

    /* -----------------------------------------------------------------
     * 14️⃣ Bind selection → mini‑AI widget
     * ----------------------------------------------------------------- */
    let mini = null; // currently open mini‑AI widget

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
        const sel = window.getSelection();
        const txt = sel.toString().trim();

        // Close history pop‑over if click is outside it.
        if (
            historyPopover &&
            !historyPopover.hidden &&
            !historyPopover.contains(e.target) &&
            !historyToggle?.contains(e.target)
        ) {
            closeHistoryPopover();
        }

        // Ignore clicks inside the toolbar or an already‑open mini‑widget.
        if (toolbar.contains(e.target) || (mini && mini.contains(e.target))) return;

        if (!txt || !isSelectionWithinContent(sel)) {
            if (mini) mini.remove();
            mini = null;
            toolbar.style.display = "none";
            return;
        }

        // Hide the (now‑unused) toolbar.
        toolbar.style.display = "none";

        const range = sel.getRangeAt(0);
        if (mini) mini.remove();
        mini = createMiniAI(range);

        const levelSelect = mini.querySelector(".ai-level");
        const getBtn = mini.querySelector(".ai-get");
        getBtn.addEventListener("click", (ev) => {
            ev.preventDefault();
            const lvl = levelSelect.value; // "simplified" | "technical"
            askAI(range, lvl);
        });
    };

    /* -----------------------------------------------------------------
     * 15️⃣ Pre‑load cached highlights *and* populate the history UI
     * ----------------------------------------------------------------- */
    const preloadExistingHighlights = async () => {
        if (!hasValidId) return; // nothing to preload for static pages

        try {
            const resp = await fetch(`${apiBase}${moduleId}/highlight/`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json(); // {answers:[{query, answer:{…}}]}

            (data.answers || []).forEach((item) => {
                const query = (item.query || "").trim();
                if (!query) return;

                const ans = item.answer || {};
                const hasS = !!ans.simplified;
                const hasT = !!ans.technical;

                if (hasS) {
                    setHighlightAnswer(query, "simplified", ans.simplified);
                    addHistoryEntry(query, "simplified");
                }
                if (hasT) {
                    setHighlightAnswer(query, "technical", ans.technical);
                    addHistoryEntry(query, "technical");
                }

                applyHighlightToQuery(query, {
                    simplified: hasS,
                    technical: hasT,
                });
            });

            syncHighlightSpans();
        } catch (e) {
            console.warn("Could not preload highlights:", e);
        }
    };

    // -----------------------------------------------------------------
    // Initialise everything
    // -----------------------------------------------------------------
    preloadExistingHighlights(); // fills maps, creates spans, populates history
    updateHistoryUI(); // in case nothing was cached

    if (historyToggle) {
        historyToggle.addEventListener("click", (ev) => {
            ev.stopPropagation();
            toggleHistoryPopover();
        });
    }

    // -----------------------------------------------------------------
    // Mouse / touch handling (same as before)
    // -----------------------------------------------------------------
    document.addEventListener("mouseup", onSelectionDone);
    document.addEventListener("touchend", (e) => setTimeout(() => onSelectionDone(e), 10));

    document.addEventListener("selectionchange", () => {
        const sel = window.getSelection();
        if (!sel || !sel.toString().trim() || !isSelectionWithinContent(sel)) {
            if (mini) mini.remove();
            mini = null;
            toolbar.style.display = "none";
        }
    });

    document.addEventListener("mousedown", (e) => {
        // Click outside of an open tooltip → close it.
        if (activeTooltip && !activeTooltip.contains(e.target)) removeTooltip();

        // Click outside any mini‑AI widget → close that widget.
        if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
            mini.remove();
            mini = null;
        }

        // Click outside toolbar → hide toolbar.
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
    document.addEventListener("scroll", removeTooltip, true);
}
