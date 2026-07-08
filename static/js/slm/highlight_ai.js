// static/js/slm/highlight_ai.js
import { csrftoken } from "./utils.js";

/**
 * Initialise the highlight‑→‑Ask‑AI behaviour.
 *
 * @param {HTMLElement} toolbar   – the floating toolbar that already exists
 *                                 (it will be hidden after a selection).
 * @param {number} moduleId        – PK of the current Module.
 * @param {HTMLElement|string} contentScope – the element or selector that should
 *                                            accept highlighting.
 */
export function initHighlightAI(toolbar, moduleId, contentScope = '.module-content-card .module-content') {
    const contentRoot = typeof contentScope === 'string'
        ? document.querySelector(contentScope)
        : contentScope;

    if (!contentRoot) return;

    const historyList = document.getElementById('highlight-history-list');
    const historyCount = document.getElementById('highlight-history-count');
    const historyToggle = document.getElementById('highlight-history-toggle');
    const historyPopover = document.getElementById('highlight-history-popover');
    const historyEntries = [];
    const highlightStates = new Map();
    const answerStore = new Map();
    let activeTooltip = null;
    let tooltipRemovalTimer = null;

    const toggleHistoryPopover = () => {
        if (!historyPopover || !historyToggle) return;
        const nextState = historyPopover.hidden;
        historyPopover.hidden = !nextState;
        historyToggle.setAttribute('aria-expanded', String(nextState));
    };

    const closeHistoryPopover = () => {
        if (!historyPopover || !historyToggle) return;
        historyPopover.hidden = true;
        historyToggle.setAttribute('aria-expanded', 'false');
    };

    const clearActiveHistoryHighlight = () => {
        if (!contentRoot) return;
        contentRoot.querySelectorAll('.highlight-marked--active').forEach((span) => {
            span.classList.remove('highlight-marked--active');
        });
    };

    const focusHighlightByQuery = (query, { scroll = true } = {}) => {
        const normalized = (query || '').trim();
        if (!normalized || !contentRoot) return;

        clearActiveHistoryHighlight();

        const matches = Array.from(contentRoot.querySelectorAll('.highlight-marked'))
            .filter((span) => {
                const spanQuery = (span.dataset.highlightQuery || span.textContent || '').trim();
                return spanQuery.toLowerCase() === normalized.toLowerCase();
            });

        if (matches.length === 0) return;

        matches.forEach((span) => {
            span.classList.add('highlight-marked--active');
            if (!span.dataset.highlightQuery) {
                span.dataset.highlightQuery = normalized;
            }
        });
        if (scroll) {
            matches[0].scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
        }
    };

    const updateHistoryUI = () => {
        if (!historyList) return;
        historyList.innerHTML = '';
        if (historyEntries.length === 0) {
            const empty = document.createElement('li');
            empty.className = 'module-content-history__item';
            empty.textContent = 'No highlights yet.';
            historyList.appendChild(empty);
        } else {
            historyEntries.slice().reverse().forEach((entry) => {
                const item = document.createElement('li');
                item.className = 'module-content-history__item';
                item.dataset.historyQuery = entry.text;
                item.setAttribute('role', 'button');
                item.setAttribute('tabindex', '0');
                item.setAttribute('title', `Jump to “${entry.text}”`);
                item.innerHTML = `
                    <span class="module-content-history__text">${entry.text}</span>
                    <span class="module-content-history__meta">${entry.levels.join(' + ')}</span>
                `;
                item.addEventListener('click', () => {
                    focusHighlightByQuery(entry.text);
                    closeHistoryPopover();
                });
                item.addEventListener('keydown', (event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        focusHighlightByQuery(entry.text);
                        closeHistoryPopover();
                    }
                });
                historyList.appendChild(item);
            });
        }
        if (historyCount) {
            historyCount.textContent = `${historyEntries.length} ${historyEntries.length === 1 ? 'item' : 'items'}`;
        }
    };

    const addHistoryEntry = (text, level) => {
        const entryText = (text || '').trim();
        if (!entryText) return;

        const existing = historyEntries.find((entry) => entry.text === entryText);
        if (existing) {
            if (!existing.levels.includes(level)) {
                existing.levels.push(level);
            }
        } else {
            historyEntries.push({ text: entryText, levels: [level] });
        }
        updateHistoryUI();
    };

    const getHighlightClassName = (state) => {
        const hasSimplified = !!state?.simplified;
        const hasTechnical = !!state?.technical;
        if (hasSimplified && hasTechnical) return 'highlight-marked highlight-marked--both';
        if (hasSimplified) return 'highlight-marked highlight-marked--simplified';
        if (hasTechnical) return 'highlight-marked highlight-marked--technical';
        return 'highlight-marked';
    };

    const setHighlightState = (query, level) => {
        const normalized = (query || '').trim();
        if (!normalized) return;

        const current = highlightStates.get(normalized) || { simplified: false, technical: false };
        current[level] = true;
        highlightStates.set(normalized, current);
    };

    const setHighlightAnswer = (query, level, answer) => {
        const normalized = (query || '').trim();
        if (!normalized) return;

        const current = answerStore.get(normalized) || {};
        current[level] = answer;
        answerStore.set(normalized, current);
        setHighlightState(normalized, level);
    };

    const buildAnswerText = (query) => {
        const normalized = (query || '').trim();
        if (!normalized) return '';

        const answers = answerStore.get(normalized) || {};
        const parts = [];
        if (answers.simplified) parts.push(`Simplified:\n${answers.simplified}`);
        if (answers.technical) parts.push(`Technical:\n${answers.technical}`);
        return parts.join('\n\n');
    };

    const removeTooltip = () => {
        if (tooltipRemovalTimer) {
            clearTimeout(tooltipRemovalTimer);
            tooltipRemovalTimer = null;
        }
        if (activeTooltip) {
            activeTooltip.remove();
            activeTooltip = null;
        }
    };

    const showTooltip = (event, span, query) => {
        const answerText = buildAnswerText(query);
        if (!answerText) return;

        removeTooltip();

        const tooltip = document.createElement('div');
        tooltip.className = 'highlight-answer-tooltip';
        tooltip.innerHTML = `<div class="highlight-answer-tooltip__body" tabindex="0">${renderMarkdown(answerText)}</div>`;
        document.body.appendChild(tooltip);

        const rect = span.getBoundingClientRect();
        const tooltipWidth = Math.min(320, window.innerWidth - 24);
        const left = Math.min(rect.left + window.scrollX, document.documentElement.clientWidth - tooltipWidth - 8);
        const top = rect.bottom + window.scrollY + 8;

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${Math.max(8, left)}px`;
        tooltip.style.maxWidth = `${tooltipWidth}px`;
        // remember the anchor span so we can reposition on scroll
        tooltip._anchorSpan = span;
        activeTooltip = tooltip;

        // Make the tooltip interactive: allow pointer events and keep it
        // visible while the mouse is over it. Clear any pending removal.
        tooltip.style.pointerEvents = 'auto';
        tooltip.addEventListener('mouseenter', () => {
            if (tooltipRemovalTimer) {
                clearTimeout(tooltipRemovalTimer);
                tooltipRemovalTimer = null;
            }
        });
        tooltip.addEventListener('mouseleave', () => removeTooltip());
        tooltip.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') removeTooltip();
        });
    };

    const repositionTooltipOnScroll = () => {
        if (!activeTooltip) return;
        // if the user is interacting with the tooltip, don't reposition/remove
        if (activeTooltip.matches(':hover')) return;

        const span = activeTooltip._anchorSpan;
        if (!span || !document.body.contains(span)) {
            removeTooltip();
            return;
        }

        // Recompute position relative to the anchor span
        const rect = span.getBoundingClientRect();
        const tooltipWidth = Math.min(320, window.innerWidth - 24);
        const left = Math.min(rect.left + window.scrollX, document.documentElement.clientWidth - tooltipWidth - 8);
        const top = rect.bottom + window.scrollY + 8;

        activeTooltip.style.top = `${top}px`;
        activeTooltip.style.left = `${Math.max(8, left)}px`;
        activeTooltip.style.maxWidth = `${tooltipWidth}px`;
    };

    const attachHighlightEvents = (span, query) => {
        if (span.dataset.tooltipBound === 'true') return;
        span.addEventListener('mouseenter', () => showTooltip(null, span, query));
        span.addEventListener('focus', () => showTooltip(null, span, query));
        span.addEventListener('mouseleave', () => {
            if (tooltipRemovalTimer) clearTimeout(tooltipRemovalTimer);
            tooltipRemovalTimer = setTimeout(() => {
                if (!activeTooltip || !activeTooltip.matches(':hover')) removeTooltip();
                tooltipRemovalTimer = null;
            }, 150);
        });
        span.addEventListener('blur', () => {
            if (tooltipRemovalTimer) clearTimeout(tooltipRemovalTimer);
            tooltipRemovalTimer = setTimeout(() => {
                if (!activeTooltip || !activeTooltip.matches(':hover')) removeTooltip();
                tooltipRemovalTimer = null;
            }, 150);
        });
        span.setAttribute('tabindex', '0');
        span.dataset.tooltipBound = 'true';
    };

    const syncHighlightSpans = () => {
        if (!contentRoot) return;
        const spans = Array.from(contentRoot.querySelectorAll('.highlight-marked'));
        spans.forEach((span) => {
            const query = span.dataset.highlightQuery || span.textContent?.trim() || '';
            if (!query) return;
            const state = highlightStates.get(query) || { simplified: false, technical: false };
            const shouldStayActive = span.classList.contains('highlight-marked--active');
            span.className = shouldStayActive
                ? `${getHighlightClassName(state)} highlight-marked--active`
                : getHighlightClassName(state);
            span.dataset.answer = buildAnswerText(query);
            attachHighlightEvents(span, query);
        });
    };

    const applyHighlightToQuery = (query, state) => {
        const normalized = (query || '').trim();
        if (!normalized) return;

        const className = getHighlightClassName(state);
        const escaped = normalized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escaped})`, 'gi');
        const walker = document.createTreeWalker(contentRoot, NodeFilter.SHOW_TEXT, {
            acceptNode: (node) => {
                if (!node.nodeValue || !node.nodeValue.includes(normalized)) return NodeFilter.FILTER_REJECT;
                if (node.parentNode && node.parentNode.closest && node.parentNode.closest('.highlight-marked')) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        });

        const textNodes = [];
        let currentNode = walker.nextNode();
        while (currentNode) {
            textNodes.push(currentNode);
            currentNode = walker.nextNode();
        }

        textNodes.forEach((textNode) => {
            const text = textNode.nodeValue || '';
            if (!regex.test(text)) return;
            regex.lastIndex = 0;
            const fragment = document.createDocumentFragment();
            let lastIndex = 0;
            let match;
            while ((match = regex.exec(text)) !== null) {
                if (match.index > lastIndex) {
                    fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
                }
                const span = document.createElement('span');
                span.className = className;
                span.dataset.highlightQuery = normalized;
                span.dataset.answer = buildAnswerText(normalized);
                span.appendChild(document.createTextNode(match[1]));
                attachHighlightEvents(span, normalized);
                fragment.appendChild(span);
                lastIndex = match.index + match[1].length;
            }
            if (lastIndex < text.length) {
                fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
            }
            if (fragment.childNodes.length > 0) {
                textNode.parentNode.replaceChild(fragment, textNode);
            }
        });
        syncHighlightSpans();
    };
    // -----------------------------------------------------------------
    // 1️⃣  Tiny “mini‑AI” widget
    // -----------------------------------------------------------------
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

        // Position just under the selection.
        const rect = range.getBoundingClientRect();
        const top = rect.bottom + window.scrollY + 6; // 6 px gap
        const left = Math.min(
            rect.left + window.scrollX,
            document.documentElement.clientWidth - mini.offsetWidth - 8
        );
        mini.style.top = `${top}px`;
        mini.style.left = `${left}px`;

        // Click‑outside → close.
        const clickOutside = (e) => {
            if (!mini.contains(e.target)) {
                mini.remove();
                document.removeEventListener("mousedown", clickOutside);
            }
        };
        document.addEventListener("mousedown", clickOutside);

        // Ensure any typing interval is cleared when the widget is removed.
        const origRemove = mini.remove.bind(mini);
        mini.remove = function () {
            if (mini._typingInterval) {
                clearInterval(mini._typingInterval);
                mini._typingInterval = null;
            }
            origRemove();
        };

        return mini;
    };

    const escapeHtml = (value) => {
        return value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    const renderMarkdown = (text) => {
        if (!text) return "";

        const escaped = escapeHtml(text);
        const lines = escaped.split(/\r?\n/);
        let html = "";
        let listType = null;
        let listOpen = false;
        let tableRows = [];
        let inTable = false;

        function closeList() {
            if (listOpen) {
                html += listType === "ol" ? "</ol>" : "</ul>";
                listOpen = false;
                listType = null;
            }
        }

        function flushTable() {
            if (!inTable || tableRows.length === 0) return;

            const cells = tableRows.map((row) => row.replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim()));
            const header = cells[0] || [];
            const separator = cells[1] || [];
            const bodyRows = cells.slice(2);
            const isTable = separator.every((cell) => /^:?-+:?$/.test(cell));

            if (isTable) {
                html += "<table class=\"message-table\"><thead><tr>";
                header.forEach((cell) => {
                    html += `<th>${inlineFormatting(cell)}</th>`;
                });
                html += "</tr></thead><tbody>";
                bodyRows.forEach((row) => {
                    html += "<tr>";
                    row.forEach((cell) => {
                        html += `<td>${inlineFormatting(cell)}</td>`;
                    });
                    html += "</tr>";
                });
                html += "</tbody></table>";
            } else {
                tableRows.forEach((row) => {
                    html += `<p>${inlineFormatting(row)}</p>`;
                });
            }

            tableRows = [];
            inTable = false;
        }

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmed = line.trim();

            const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
            if (headingMatch) {
                closeList();
                flushTable();
                const level = Math.min(6, headingMatch[1].length);
                const content = inlineFormatting(headingMatch[2]);
                html += `<h${level}>${content}</h${level}>`;
                continue;
            }

            if (/^(?:---|\*\*\*|___)\s*$/.test(trimmed)) {
                closeList();
                flushTable();
                html += "<hr class=\"message-hr\"/>";
                continue;
            }

            if (/^>\s?/.test(trimmed)) {
                closeList();
                flushTable();
                const quote = trimmed.replace(/^>\s?/, "");
                html += `<blockquote>${inlineFormatting(quote)}</blockquote>`;
                continue;
            }

            if (/^```/.test(trimmed)) {
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

            if (/^!\[.*\]\(.*\)$/.test(trimmed)) {
                closeList();
                flushTable();
                html += trimmed.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => {
                    return `<div class="message-image"><img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}"></div>`;
                });
                continue;
            }

            if (/^\s*\|.*\|\s*$/.test(line)) {
                closeList();
                inTable = true;
                tableRows.push(line);
                continue;
            }

            if (inTable && trimmed === "") {
                flushTable();
            }

            if (/^\d+\.\s+/.test(trimmed)) {
                flushTable();
                const content = trimmed.replace(/^\d+\.\s+/, "");
                if (!listOpen || listType !== "ol") {
                    closeList();
                    listType = "ol";
                    listOpen = true;
                    html += "<ol>";
                }
                html += `<li>${inlineFormatting(content)}</li>`;
                continue;
            }

            if (/^[-*+]\s+/.test(trimmed)) {
                flushTable();
                const content = trimmed.replace(/^[-*+]\s+/, "");
                if (!listOpen || listType !== "ul") {
                    closeList();
                    listType = "ul";
                    listOpen = true;
                    html += "<ul>";
                }
                html += `<li>${inlineFormatting(content)}</li>`;
                continue;
            }

            if (trimmed === "") {
                closeList();
                flushTable();
                html += "<p></p>";
                continue;
            }

            closeList();
            flushTable();
            html += `<p>${inlineFormatting(trimmed)}</p>`;
        }

        closeList();
        flushTable();
        return html;
    };

    const inlineFormatting = (text) => {
        return text
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => {
                return `<span class="inline-image"><img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}"></span>`;
            })
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
                return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
            })
            .replace(/\*\*([^*]+)\*\*/g, (_, bold) => `<strong>${escapeHtml(bold)}</strong>`)
            .replace(/\*([^*]+)\*/g, (_, italic) => `<em>${escapeHtml(italic)}</em>`)
            .replace(/`([^`]+)`/g, (_, code) => `<code>${escapeHtml(code)}</code>`);
    };

    const renderAnswer = (mini, html, cached) => {
        const box = mini.querySelector(".ai-answer");
        box.classList.remove("hidden");

        // If the answer is cached, render immediately.
        if (cached) {
            box.innerHTML = `
                ${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ''}
                <div class="ai-answer-content">${renderMarkdown(html)}</div>
            `;
            return;
        }

        // Non-cached: show a typewriter animation of the plain text,
        // then replace with the full rendered markdown HTML.
        box.innerHTML = `${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ''}`;
        const typingContainer = document.createElement('div');
        typingContainer.className = 'ai-answer-typing';
        typingContainer.setAttribute('aria-live', 'polite');
        box.appendChild(typingContainer);

        // Convert rendered markdown to HTML, then extract plain text for typing.
        const renderedHtml = renderMarkdown(html);
        const tmp = document.createElement('div');
        tmp.innerHTML = renderedHtml;
        const plain = tmp.textContent || tmp.innerText || '';

        // Clear any existing typing interval for this mini widget.
        if (mini._typingInterval) {
            clearInterval(mini._typingInterval);
            mini._typingInterval = null;
        }

        // Typing state
        let index = 0;
        const speed = 16 + Math.floor(Math.random() * 18); // 16-34ms per char
        const caret = document.createElement('span');
        caret.className = 'ai-typing-caret';
        caret.textContent = '\u25AE';
        typingContainer.appendChild(caret);

        const typeNext = () => {
            if (index >= plain.length) {
                // Finished typing: replace with full rendered HTML
                box.innerHTML = `${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ''}`;
                const final = document.createElement('div');
                final.className = 'ai-answer-content';
                final.innerHTML = renderedHtml;
                box.appendChild(final);
                mini._typingInterval = null;
                return;
            }

            // Insert next character before the caret
            const char = plain.charAt(index);
            const node = document.createTextNode(char);
            typingContainer.insertBefore(node, caret);
            index += 1;
        };

        // Start typing with setInterval; keep reference so we can cancel.
        mini._typingInterval = setInterval(typeNext, speed);
    };

    // -----------------------------------------------------------------
    // 2️⃣  Ask the AI – only the selected level
    // -----------------------------------------------------------------
    const askAI = async (range, level) => {
        const sel   = window.getSelection();
        const query = sel.toString().trim();
        if (!query) return;

        // Show a temporary “thinking…” on the button.
        const mini   = createMiniAI(range);
        const btn    = mini.querySelector(".ai-get");
        const oldTxt = btn.textContent;
        btn.textContent = "Thinking…";
        btn.disabled    = true;

        try {
            const resp = await fetch(
                `/slm/api/modules/${moduleId}/highlight/`,
                {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrftoken,
                    },
                    body: JSON.stringify({ query, level }),   // <-- send level
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
            renderAnswer(mini,
                "<em>Sorry – the AI service could not be reached.</em>",
                false);
        } finally {
            btn.textContent = oldTxt;
            btn.disabled    = false;
        }
    };

    // -----------------------------------------------------------------
    // 3️⃣  Visual marking of the fragment
    // -----------------------------------------------------------------
    const markSelection = (range, level) => {
        const selectedText = range.toString().trim();
        if (!selectedText) return;

        const span = document.createElement("span");
        span.className = getHighlightClassName({
            simplified: level === 'simplified',
            technical: level === 'technical'
        });
        span.dataset.highlightQuery = selectedText;
        span.dataset.answer = buildAnswerText(selectedText);
        span.appendChild(range.extractContents());
        attachHighlightEvents(span, selectedText);
        range.insertNode(span);
    };

    // -----------------------------------------------------------------
    // 4️⃣  Bind selection → mini‑AI widget
    // -----------------------------------------------------------------
    let mini = null; // current widget

    const isSelectionWithinContent = (selection) => {
        if (!selection || selection.rangeCount === 0) return false;

        const range = selection.getRangeAt(0);
        const checkNode = (node) => {
            let current = node;
            while (current) {
                if (current === contentRoot) return true;
                current = current.parentNode;
            }
            return false;
        };

        return checkNode(range.startContainer) && checkNode(range.endContainer);
    };

    const onSelectionDone = (event) => {
        const sel  = window.getSelection();
        const text = sel.toString().trim();

        if (historyPopover && !historyPopover.hidden && !historyPopover.contains(event.target) && !historyToggle?.contains(event.target)) {
            closeHistoryPopover();
        }

        // Ignore clicks inside the old toolbar or an already‑open mini.
        if (toolbar.contains(event.target) || (mini && mini.contains(event.target))) {
            return;
        }

        if (!text || !isSelectionWithinContent(sel)) {
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

        // Wire the button.
        const levelSelect = mini.querySelector(".ai-level");
        const getBtn      = mini.querySelector(".ai-get");
        getBtn.addEventListener("click", (e) => {
            e.preventDefault();
            const level = levelSelect.value;   // "simplified" | "technical"
            askAI(range, level);
        });
    };

    // -----------------------------------------------------------------
    // 5️⃣  Mouse / touch handling (same as before)
    // -----------------------------------------------------------------
    const preloadExistingHighlights = async () => {
        try {
            const resp = await fetch(`/slm/api/modules/${moduleId}/highlight/`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            (data.answers || []).forEach((item) => {
                const query = (item.query || '').trim();
                if (!query) return;
                const states = item.answer || {};
                const hasSimplified = !!states.simplified;
                const hasTechnical = !!states.technical;
                if (hasSimplified || hasTechnical) {
                    if (hasSimplified) {
                        setHighlightAnswer(query, 'simplified', states.simplified);
                        addHistoryEntry(query, 'simplified');
                    }
                    if (hasTechnical) {
                        setHighlightAnswer(query, 'technical', states.technical);
                        addHistoryEntry(query, 'technical');
                    }
                    applyHighlightToQuery(query, { simplified: hasSimplified, technical: hasTechnical });
                }
            });
            syncHighlightSpans();
        } catch (e) {
            console.warn('Could not preload highlights:', e);
        }
    };

    preloadExistingHighlights();
    updateHistoryUI();

    if (historyToggle) {
        historyToggle.addEventListener('click', (event) => {
            event.stopPropagation();
            toggleHistoryPopover();
        });
    }

    document.addEventListener("mouseup", onSelectionDone);
    document.addEventListener('click', (event) => {
        if (!historyPopover || historyPopover.hidden) return;
        if (!historyPopover.contains(event.target) && !historyToggle?.contains(event.target)) {
            closeHistoryPopover();
        }
    });
    document.addEventListener("scroll", repositionTooltipOnScroll, true);
    document.addEventListener("mousedown", (e) => {
        if (activeTooltip && !activeTooltip.contains(e.target)) {
            removeTooltip();
        }
    });
    document.addEventListener("touchend", (e) => setTimeout(() => onSelectionDone(e), 10));
    document.addEventListener("selectionchange", () => {
        const sel = window.getSelection();
        if (!sel || sel.toString().trim().length === 0 || !isSelectionWithinContent(sel)) {
            if (mini) mini.remove();
            mini = null;
            toolbar.style.display = "none";
        }
    });
    document.addEventListener("mousedown", (e) => {
        if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
            mini.remove();
            mini = null;
        }
    });
    document.addEventListener("touchstart", (e) => {
        if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
            mini.remove();
            mini = null;
        }
    });
}
