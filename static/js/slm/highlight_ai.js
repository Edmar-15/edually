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
    // -------------------------------------------------------------
    // 1️⃣  Resolve the content root element
    // -------------------------------------------------------------
    const contentRoot = typeof contentScope === 'string'
        ? document.querySelector(contentScope)
        : contentScope;

    if (!contentRoot) return;

    // -------------------------------------------------------------
    // 2️⃣  UI elements for the highlight‑history pop‑over
    // -------------------------------------------------------------
    const historyList = document.getElementById('highlight-history-list');
    const historyCount = document.getElementById('highlight-history-count');
    const historyToggle = document.getElementById('highlight-history-toggle');
    const historyPopover = document.getElementById('highlight-history-popover');

    const historyEntries = [];

    // -------------------------------------------------------------
    // 3️⃣  Helper – make everything case‑insensitive
    // -------------------------------------------------------------
    /**
     * Normalise a raw query string.
     *  • trim surrounding whitespace
     *  • lower‑case – DB stores lower‑case, UI must treat it case‑insensitive
     */
    const normalise = (txt) => (txt || '').trim().toLowerCase();

    // Internal maps are keyed by the *normalised* query.
    const highlightStates = new Map();   // { simplified: bool, technical: bool }
    const answerStore = new Map();        // { simplified: html, technical: html }

    // -------------------------------------------------------------
    // 4️⃣  History UI helpers
    // -------------------------------------------------------------
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
                item.innerHTML = `
                    <span class="module-content-history__text">${entry.text}</span>
                    <span class="module-content-history__meta">${entry.levels.join(' + ')}</span>
                `;
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

        const existing = historyEntries.find((e) => e.text === entryText);
        if (existing) {
            if (!existing.levels.includes(level)) {
                existing.levels.push(level);
            }
        } else {
            historyEntries.push({ text: entryText, levels: [level] });
        }
        updateHistoryUI();
    };

    // -------------------------------------------------------------
    // 5️⃣  Highlight‑class handling
    // -------------------------------------------------------------
    const getHighlightClassName = (state) => {
        const hasSimplified = !!state?.simplified;
        const hasTechnical = !!state?.technical;
        if (hasSimplified && hasTechnical) return 'highlight-marked highlight-marked--both';
        if (hasSimplified) return 'highlight-marked highlight-marked--simplified';
        if (hasTechnical) return 'highlight-marked highlight-marked--technical';
        return 'highlight-marked';
    };

    const setHighlightState = (query, level) => {
        const normalized = normalise(query);
        if (!normalized) return;

        const current = highlightStates.get(normalized) || { simplified: false, technical: false };
        current[level] = true;
        highlightStates.set(normalized, current);
    };

    const setHighlightAnswer = (query, level, answer) => {
        const normalized = normalise(query);
        if (!normalized) return;

        const current = answerStore.get(normalized) || {};
        current[level] = answer;
        answerStore.set(normalized, current);
        setHighlightState(normalized, level);
    };

    const buildAnswerText = (query) => {
        const normalized = normalise(query);
        if (!normalized) return '';

        const answers = answerStore.get(normalized) || {};
        const parts = [];
        if (answers.simplified) parts.push(`Simplified:\n${answers.simplified}`);
        if (answers.technical) parts.push(`Technical:\n${answers.technical}`);
        return parts.join('\n\n');
    };

    // -------------------------------------------------------------
    // 6️⃣  Tooltip handling (hover / focus)
    // -------------------------------------------------------------
    let activeTooltip = null;

    const removeTooltip = () => {
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
        tooltip.innerHTML = `<div class="highlight-answer-tooltip__body">${renderMarkdown(answerText)}</div>`;
        document.body.appendChild(tooltip);

        const rect = span.getBoundingClientRect();
        const tooltipWidth = Math.min(320, window.innerWidth - 24);
        const left = Math.min(rect.left + window.scrollX,
                              document.documentElement.clientWidth - tooltipWidth - 8);
        const top = rect.bottom + window.scrollY + 8;

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${Math.max(8, left)}px`;
        tooltip.style.maxWidth = `${tooltipWidth}px`;
        activeTooltip = tooltip;
    };

    const attachHighlightEvents = (span, query) => {
        if (span.dataset.tooltipBound === 'true') return;
        span.addEventListener('mouseenter', () => showTooltip(null, span, query));
        span.addEventListener('focus', () => showTooltip(null, span, query));
        span.addEventListener('mouseleave', removeTooltip);
        span.addEventListener('blur', removeTooltip);
        span.setAttribute('tabindex', '0');
        span.dataset.tooltipBound = 'true';
    };

    // -------------------------------------------------------------
    // 7️⃣  Keep the DOM in sync when the internal maps change
    // -------------------------------------------------------------
    const syncHighlightSpans = () => {
        if (!contentRoot) return;
        const spans = Array.from(contentRoot.querySelectorAll('.highlight-marked'));
        spans.forEach((span) => {
            // `data‑highlight‑query` is stored lower‑cased; fall back to a lower‑cased
            // version of the inner text just in case.
            const query = span.dataset.highlightQuery ||
                          span.textContent?.trim().toLowerCase() ||
                          '';
            if (!query) return;
            const state = highlightStates.get(query) || { simplified: false, technical: false };
            span.className = getHighlightClassName(state);
            span.dataset.answer = buildAnswerText(query);
            attachHighlightEvents(span, query);
        });
    };

    // -------------------------------------------------------------
    // 8️⃣  Apply a highlight to **all** occurrences of a query
    // -------------------------------------------------------------
    const applyHighlightToQuery = (query, state) => {
        const normalized = normalise(query);
        if (!normalized) return;

        const className = getHighlightClassName(state);
        const escaped = normalized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escaped})`, 'gi');   // `i` = case‑insensitive

        // Walk text nodes that still contain the (lower‑cased) query.
        const walker = document.createTreeWalker(contentRoot, NodeFilter.SHOW_TEXT, {
            acceptNode: (node) => {
                if (!node.nodeValue) return NodeFilter.FILTER_REJECT;
                if (!node.nodeValue.toLowerCase().includes(normalized)) return NodeFilter.FILTER_REJECT;
                if (node.parentNode && node.parentNode.closest && node.parentNode.closest('.highlight-marked')) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        });

        const textNodes = [];
        let cur = walker.nextNode();
        while (cur) {
            textNodes.push(cur);
            cur = walker.nextNode();
        }

        textNodes.forEach((textNode) => {
            const text = textNode.nodeValue || '';
            if (!regex.test(text)) return;
            regex.lastIndex = 0;
            const fragment = document.createDocumentFragment();
            let lastIdx = 0;
            let match;
            while ((match = regex.exec(text)) !== null) {
                if (match.index > lastIdx) {
                    fragment.appendChild(document.createTextNode(text.slice(lastIdx, match.index)));
                }
                const span = document.createElement('span');
                span.className = className;
                // Store the *lower‑cased* key, but keep the original casing in the UI.
                span.dataset.highlightQuery = normalized;
                span.dataset.answer = buildAnswerText(normalized);
                span.appendChild(document.createTextNode(match[1])); // show original case
                attachHighlightEvents(span, normalized);
                fragment.appendChild(span);
                lastIdx = match.index + match[1].length;
            }
            if (lastIdx < text.length) {
                fragment.appendChild(document.createTextNode(text.slice(lastIdx)));
            }
            if (fragment.childNodes.length) {
                textNode.parentNode.replaceChild(fragment, textNode);
            }
        });

        syncHighlightSpans();
    };

    // -------------------------------------------------------------
    // 9️⃣  Mini‑AI widget (the small pop‑over that appears after a selection)
    // -------------------------------------------------------------
    const createMiniAI = (range) => {
        const mini = document.createElement('div');
        mini.className = 'ai-mini';
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
        const top = rect.bottom + window.scrollY + 6; // 6 px gap
        const left = Math.min(
            rect.left + window.scrollX,
            document.documentElement.clientWidth - mini.offsetWidth - 8
        );
        mini.style.top = `${top}px`;
        mini.style.left = `${left}px`;

        const clickOutside = (e) => {
            if (!mini.contains(e.target)) {
                mini.remove();
                document.removeEventListener('mousedown', clickOutside);
            }
        };
        document.addEventListener('mousedown', clickOutside);
        return mini;
    };

    // -------------------------------------------------------------
    // 10️⃣  Markdown → HTML (tiny, self‑contained, no external lib)
    // -------------------------------------------------------------
    const escapeHtml = (value) => {
        return value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
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

    const renderMarkdown = (text) => {
        if (!text) return '';
        const escaped = escapeHtml(text);
        const lines = escaped.split(/\r?\n/);
        let html = '';
        let listType = null;
        let listOpen = false;
        let tableRows = [];
        let inTable = false;

        const closeList = () => {
            if (listOpen) {
                html += listType === 'ol' ? '</ol>' : '</ul>';
                listOpen = false;
                listType = null;
            }
        };

        const flushTable = () => {
            if (!inTable || tableRows.length === 0) return;
            const cells = tableRows.map((row) =>
                row.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
            );
            const header = cells[0] || [];
            const separator = cells[1] || [];
            const bodyRows = cells.slice(2);
            const isTable = separator.every((c) => /^:?-+:?$/.test(c));

            if (isTable) {
                html += '<table class="message-table"><thead><tr>';
                header.forEach((cell) => {
                    html += `<th>${inlineFormatting(cell)}</th>`;
                });
                html += '</tr></thead><tbody>';
                bodyRows.forEach((row) => {
                    html += '<tr>';
                    row.forEach((cell) => {
                        html += `<td>${inlineFormatting(cell)}</td>`;
                    });
                    html += '</tr>';
                });
                html += '</tbody></table>';
            } else {
                tableRows.forEach((row) => {
                    html += `<p>${inlineFormatting(row)}</p>`;
                });
            }
            tableRows = [];
            inTable = false;
        };

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const trimmed = line.trim();

            const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
            if (heading) {
                closeList();
                flushTable();
                const level = Math.min(6, heading[1].length);
                html += `<h${level}>${inlineFormatting(heading[2])}</h${level}>`;
                continue;
            }

            if (/^(---|\*\*\*|___)\s*$/.test(trimmed)) {
                closeList();
                flushTable();
                html += '<hr class="message-hr"/>';
                continue;
            }

            if (/^>\s?/.test(trimmed)) {
                closeList();
                flushTable();
                html += `<blockquote>${inlineFormatting(trimmed.replace(/^>\s?/, ''))}</blockquote>`;
                continue;
            }

            if (/^```/.test(trimmed)) {
                closeList();
                flushTable();
                let code = '';
                i++;
                while (i < lines.length && !/^```/.test(lines[i].trim())) {
                    code += lines[i] + '\n';
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

            if (inTable && trimmed === '') {
                flushTable();
            }

            if (/^\d+\.\s+/.test(trimmed)) {
                flushTable();
                const content = trimmed.replace(/^\d+\.\s+/, '');
                if (!listOpen || listType !== 'ol') {
                    closeList();
                    listType = 'ol';
                    listOpen = true;
                    html += '<ol>';
                }
                html += `<li>${inlineFormatting(content)}</li>`;
                continue;
            }

            if (/^[-*+]\s+/.test(trimmed)) {
                flushTable();
                const content = trimmed.replace(/^[-*+]\s+/, '');
                if (!listOpen || listType !== 'ul') {
                    closeList();
                    listType = 'ul';
                    listOpen = true;
                    html += '<ul>';
                }
                html += `<li>${inlineFormatting(content)}</li>`;
                continue;
            }

            if (trimmed === '') {
                closeList();
                flushTable();
                html += '<p></p>';
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

    const renderAnswer = (mini, html, cached) => {
        const box = mini.querySelector('.ai-answer');
        box.innerHTML = `
            ${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ''}
            <div class="ai-answer-content">${renderMarkdown(html)}</div>
        `;
        box.classList.remove('hidden');
    };

    // -------------------------------------------------------------
    // 11️⃣  Ask the AI (POST → /highlight/)
    // -------------------------------------------------------------
    const askAI = async (range, level) => {
        const sel = window.getSelection();
        const query = sel.toString().trim();
        if (!query) return;

        const mini = createMiniAI(range);
        const btn = mini.querySelector('.ai-get');
        const oldTxt = btn.textContent;
        btn.textContent = 'Thinking…';
        btn.disabled = true;

        try {
            const resp = await fetch(
                `/slm/api/modules/${moduleId}/highlight/`,
                {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken,
                    },
                    body: JSON.stringify({ query, level }), // send the exact user text
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
            console.error('AI request failed:', err);
            renderAnswer(mini,
                '<em>Sorry – the AI service could not be reached.</em>',
                false);
        } finally {
            btn.textContent = oldTxt;
            btn.disabled = false;
        }
    };

    // -------------------------------------------------------------
    // 12️⃣  Visual marking of the selected fragment (wrap in <span>)
    // -------------------------------------------------------------
    const markSelection = (range, level) => {
        const selectedText = range.toString().trim();
        if (!selectedText) return;

        const normalised = normalise(selectedText); // lower‑cased key for storage
        const span = document.createElement('span');
        span.className = getHighlightClassName({
            simplified: level === 'simplified',
            technical: level === 'technical',
        });
        span.dataset.highlightQuery = normalised;
        span.dataset.answer = buildAnswerText(normalised);
        span.appendChild(range.extractContents());
        attachHighlightEvents(span, normalised);
        range.insertNode(span);
    };

    // -------------------------------------------------------------
    // 13️⃣  Bind selection → mini‑AI widget
    // -------------------------------------------------------------
    let mini = null; // currently open mini‑AI widget (if any)

    const isSelectionWithinContent = (selection) => {
        if (!selection || selection.rangeCount === 0) return false;
        const range = selection.getRangeAt(0);
        const checkNode = (node) => {
            let cur = node;
            while (cur) {
                if (cur === contentRoot) return true;
                cur = cur.parentNode;
            }
            return false;
        };
        return checkNode(range.startContainer) && checkNode(range.endContainer);
    };

    const onSelectionDone = (event) => {
        const sel = window.getSelection();
        const text = sel.toString().trim();

        // Close the history pop‑over if it is open and the click is outside.
        if (historyPopover && !historyPopover.hidden &&
            !historyPopover.contains(event.target) &&
            !historyToggle?.contains(event.target)) {
            closeHistoryPopover();
        }

        // Ignore clicks inside the toolbar or an already‑open mini‑widget.
        if (toolbar.contains(event.target) || (mini && mini.contains(event.target))) {
            return;
        }

        if (!text || !isSelectionWithinContent(sel)) {
            if (mini) mini.remove();
            mini = null;
            toolbar.style.display = 'none';
            return;
        }

        // Hide the (now‑unused) toolbar.
        toolbar.style.display = 'none';

        const range = sel.getRangeAt(0);
        if (mini) mini.remove();
        mini = createMiniAI(range);

        const levelSelect = mini.querySelector('.ai-level');
        const getBtn = mini.querySelector('.ai-get');
        getBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const level = levelSelect.value; // "simplified" | "technical"
            askAI(range, level);
        });
    };

    // -------------------------------------------------------------
    // 14️⃣  Mouse / touch handling (same as before)
    // -------------------------------------------------------------
    const preloadExistingHighlights = async () => {
        try {
            const resp = await fetch(`/slm/api/modules/${moduleId}/highlight/`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json(); // {answers:[{query,…}]}
            (data.answers || []).forEach((item) => {
                const query = (item.query || '').trim();
                if (!query) return;
                const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`(${escaped})`, 'gi');
                // Insert the span with the *lower‑cased* query stored in the data‑attr.
                contentRoot.innerHTML = contentRoot.innerHTML.replace(regex,
                    `<span class="highlight-marked" data-highlight-query="${query.toLowerCase()}">$1</span>`);
                // Populate internal maps so tooltips work.
                const states = item.answer || {};
                const hasSimplified = !!states.simplified;
                const hasTechnical = !!states.technical;
                if (hasSimplified) setHighlightAnswer(query, 'simplified', states.simplified);
                if (hasTechnical) setHighlightAnswer(query, 'technical', states.technical);
            });
            syncHighlightSpans();
        } catch (e) {
            console.warn('Could not preload highlights:', e);
        }
    };

    // -----------------------------------------------------------------
    // Initialise everything
    // -----------------------------------------------------------------
    preloadExistingHighlights();
    updateHistoryUI();

    if (historyToggle) {
        historyToggle.addEventListener('click', (event) => {
            event.stopPropagation();
            toggleHistoryPopover();
        });
    }

    document.addEventListener('mouseup', onSelectionDone);
    document.addEventListener('touchend', (e) => setTimeout(() => onSelectionDone(e), 10));
    document.addEventListener('selectionchange', () => {
        const sel = window.getSelection();
        if (!sel || sel.toString().trim().length === 0 || !isSelectionWithinContent(sel)) {
            if (mini) mini.remove();
            mini = null;
            toolbar.style.display = 'none';
        }
    });
    document.addEventListener('mousedown', (e) => {
        if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
            mini.remove();
            mini = null;
        }
        if (!toolbar.contains(e.target)) toolbar.style.display = 'none';
    });
    document.addEventListener('touchstart', (e) => {
        if (mini && !mini.contains(e.target) && !toolbar.contains(e.target)) {
            mini.remove();
            mini = null;
        }
        if (!toolbar.contains(e.target)) toolbar.style.display = 'none';
    });
    document.addEventListener('scroll', removeTooltip, true);
    document.addEventListener('mousedown', (e) => {
        if (activeTooltip && !activeTooltip.contains(e.target)) {
            removeTooltip();
        }
    });
}
