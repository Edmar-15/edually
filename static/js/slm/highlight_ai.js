// static/js/slm/highlight_ai.js
import { csrftoken } from "./utils.js";

/**
 * Initialise the highlight‑→‑Ask‑AI behaviour.
 *
 * @param {HTMLElement} toolbar        – the floating toolbar that already exists
 *                                      (it will be hidden after a selection).
 * @param {number}       moduleId      – PK of the current Module.
 * @param {HTMLElement|string} contentScope – the element or selector that should
 *                                          accept highlighting.
 */
export function initHighlightAI(toolbar, moduleId,
                               contentScope = '.module-content-card .module-content') {

    // -----------------------------------------------------------------
    // 1️⃣ Resolve the content root element
    // -----------------------------------------------------------------
    const contentRoot = typeof contentScope === 'string'
        ? document.querySelector(contentScope)
        : contentScope;
    if (!contentRoot) return;

    // -----------------------------------------------------------------
    // 2️⃣ History UI elements
    // -----------------------------------------------------------------
    const historyList   = document.getElementById('highlight-history-list');
    const historyCount  = document.getElementById('highlight-history-count');
    const historyToggle = document.getElementById('highlight-history-toggle');
    const historyPopover= document.getElementById('highlight-history-popover');

    const historyEntries = [];
    const highlightStates = new Map();
    const answerStore = new Map();
    let activeTooltip = null;

<<<<<<< HEAD
=======
    // -----------------------------------------------------------------
    // 3️⃣ Normalise everything to lower‑case (DB stores lower‑case)
    // -----------------------------------------------------------------
    const normalise = (txt) => (txt || '').trim().toLowerCase();

    // Maps keyed by the *normalised* query
    const highlightStates = new Map();   // {simplified:bool, technical:bool}
    const answerStore      = new Map();   // {simplified:'html', technical:'html'}

    // -----------------------------------------------------------------
    // 4️⃣ History UI helpers
    // -----------------------------------------------------------------
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
    const toggleHistoryPopover = () => {
        if (!historyPopover || !historyToggle) return;
        const next = historyPopover.hidden;
        historyPopover.hidden = !next;
        historyToggle.setAttribute('aria-expanded', String(next));
    };
    const closeHistoryPopover = () => {
        if (!historyPopover || !historyToggle) return;
        historyPopover.hidden = true;
        historyToggle.setAttribute('aria-expanded', 'false');
    };
<<<<<<< HEAD

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

=======
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
    const updateHistoryUI = () => {
        if (!historyList) return;
        historyList.innerHTML = '';
        if (historyEntries.length === 0) {
            const empty = document.createElement('li');
            empty.className = 'module-content-history__item';
            empty.textContent = 'No highlights yet.';
            historyList.appendChild(empty);
        } else {
<<<<<<< HEAD
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
=======
            historyEntries.slice().reverse().forEach(entry => {
                const li = document.createElement('li');
                li.className = 'module-content-history__item';
                li.innerHTML = `
                    <span class="module-content-history__text">${entry.text}</span>
                    <span class="module-content-history__meta">${entry.levels.join(' + ')}</span>
                `;
                historyList.appendChild(li);
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
            });
        }
        if (historyCount) {
            historyCount.textContent = `${historyEntries.length} ${historyEntries.length === 1 ? 'item' : 'items'}`;
        }
    };
    const addHistoryEntry = (text, level) => {
        const clean = (text || '').trim();
        if (!clean) return;
        const existing = historyEntries.find(e => e.text === clean);
        if (existing) {
            if (!existing.levels.includes(level)) existing.levels.push(level);
        } else {
            historyEntries.push({text: clean, levels: [level]});
        }
        updateHistoryUI();
    };

    // -----------------------------------------------------------------
    // 5️⃣ Highlight state / answer storage
    // -----------------------------------------------------------------
    const setHighlightState = (query, level) => {
        const q = normalise(query);
        if (!q) return;
        const cur = highlightStates.get(q) || {simplified:false, technical:false};
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
        if (!q) return '';
        const ans = answerStore.get(q) || {};
        const parts = [];
        if (ans.simplified) parts.push(`Simplified:\n${ans.simplified}`);
        if (ans.technical)   parts.push(`Technical:\n${ans.technical}`);
        return parts.join('\n\n');
    };

    // -----------------------------------------------------------------
    // 6️⃣ CSS class helper
    // -----------------------------------------------------------------
    const getHighlightClassName = (state) => {
        const simp = !!state?.simplified;
        const tech = !!state?.technical;
        if (simp && tech) return 'highlight-marked highlight-marked--both';
        if (simp)          return 'highlight-marked highlight-marked--simplified';
        if (tech)          return 'highlight-marked highlight-marked--technical';
        return 'highlight-marked';
    };

    // -----------------------------------------------------------------
    // 7️⃣ Tooltip (hover / focus) handling
    // -----------------------------------------------------------------
    let activeTooltip = null;
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
    const showTooltip = (span, query) => {
        const answer = buildAnswerText(query);
        if (!answer) return;
        removeTooltip();
<<<<<<< HEAD

        const tooltip = document.createElement('div');
        tooltip.className = 'highlight-answer-tooltip';
        tooltip.innerHTML = `<div class="highlight-answer-tooltip__body" tabindex="0">${renderMarkdown(answerText)}</div>`;
        document.body.appendChild(tooltip);

=======
        const tip = document.createElement('div');
        tip.className = 'highlight-answer-tooltip';
        tip.innerHTML = `<div class="highlight-answer-tooltip__body">${renderMarkdown(answer)}</div>`;
        document.body.appendChild(tip);
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
        const rect = span.getBoundingClientRect();
        const maxW = Math.min(320, window.innerWidth - 24);
        const left = Math.min(rect.left + window.scrollX,
<<<<<<< HEAD
                              document.documentElement.clientWidth - tooltipWidth - 8);
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
=======
                              document.documentElement.clientWidth - maxW - 8);
        const top  = rect.bottom + window.scrollY + 8;
        tip.style.top = `${top}px`;
        tip.style.left = `${Math.max(8, left)}px`;
        tip.style.maxWidth = `${maxW}px`;
        activeTooltip = tip;
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
    };
    const attachHighlightEvents = (span, query) => {
        if (span.dataset.tooltipBound === 'true') return;
<<<<<<< HEAD
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
=======
        span.addEventListener('mouseenter', () => showTooltip(span, query));
        span.addEventListener('focus',    () => showTooltip(span, query));
        span.addEventListener('mouseleave', removeTooltip);
        span.addEventListener('blur',        removeTooltip);
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
        span.setAttribute('tabindex', '0');
        span.dataset.tooltipBound = 'true';
    };

    // -----------------------------------------------------------------
    // 8️⃣ Keep existing spans in sync with the internal maps
    // -----------------------------------------------------------------
    const syncHighlightSpans = () => {
        if (!contentRoot) return;
        const spans = Array.from(contentRoot.querySelectorAll('.highlight-marked'));
        spans.forEach(span => {
            const query = span.dataset.highlightQuery ||
                          span.textContent?.trim().toLowerCase() || '';
            if (!query) return;
<<<<<<< HEAD
            const state = highlightStates.get(query) || { simplified: false, technical: false };
            const shouldStayActive = span.classList.contains('highlight-marked--active');
            span.className = shouldStayActive
                ? `${getHighlightClassName(state)} highlight-marked--active`
                : getHighlightClassName(state);
=======
            const state = highlightStates.get(query) || {simplified:false, technical:false};
            span.className = getHighlightClassName(state);
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
            span.dataset.answer = buildAnswerText(query);
            attachHighlightEvents(span, query);
        });
    };

    // -----------------------------------------------------------------
    // 9️⃣ Apply a highlight to *all* matches of a query
    // -----------------------------------------------------------------
    const applyHighlightToQuery = (query, state) => {
        const q = normalise(query);
        if (!q) return;
        const className = getHighlightClassName(state);
        const escaped   = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex     = new RegExp(`(${escaped})`, 'gi');   // case‑insensitive

        // Walk through text nodes that are not already inside a highlight.
        const walker = document.createTreeWalker(contentRoot, NodeFilter.SHOW_TEXT, {
            acceptNode: (node) => {
                if (!node.nodeValue) return NodeFilter.FILTER_REJECT;
                if (!node.nodeValue.toLowerCase().includes(q)) return NodeFilter.FILTER_REJECT;
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

        textNodes.forEach(textNode => {
            const txt = textNode.nodeValue || '';
            if (!regex.test(txt)) return;
            regex.lastIndex = 0;
            const frag = document.createDocumentFragment();
            let last = 0;
            let match;
            while ((match = regex.exec(txt)) !== null) {
                if (match.index > last) {
                    frag.appendChild(document.createTextNode(txt.slice(last, match.index)));
                }
                const span = document.createElement('span');
                span.className = className;
                // Store the lower‑cased key, display the original matched text.
                span.dataset.highlightQuery = q;
                span.dataset.answer        = buildAnswerText(q);
                span.appendChild(document.createTextNode(match[1]));
                attachHighlightEvents(span, q);
                frag.appendChild(span);
                last = match.index + match[1].length;
            }
            if (last < txt.length) {
                frag.appendChild(document.createTextNode(txt.slice(last)));
            }
            textNode.parentNode.replaceChild(frag, textNode);
        });

        syncHighlightSpans();
    };

    // -----------------------------------------------------------------
    // 🔟 Mini‑AI widget (the tiny box that shows after a selection)
    // -----------------------------------------------------------------
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
                document.removeEventListener('mousedown', clickOutside);
            }
        };
        document.addEventListener("mousedown", clickOutside);

        return mini;
    };

    // -----------------------------------------------------------------
    // 11️⃣ Markdown → HTML (tiny renderer – no external libs)
    // -----------------------------------------------------------------
    const escapeHtml = (v) =>
        v.replace(/&/g, '&amp;')
         .replace(/</g, '&lt;')
         .replace(/>/g, '&gt;')
         .replace(/"/g, '&quot;')
         .replace(/'/g, '&#39;');

    const inlineFormatting = (txt) => txt
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, a, s) =>
            `<span class="inline-image"><img src="${escapeHtml(s)}" alt="${escapeHtml(a)}"></span>`)
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, l, h) =>
            `<a href="${escapeHtml(h)}" target="_blank" rel="noopener noreferrer">${escapeHtml(l)}</a>`)
        .replace(/\*\*([^*]+)\*\*/g, (_, b) => `<strong>${escapeHtml(b)}</strong>`)
        .replace(/\*([^*]+)\*/g, (_, i) => `<em>${escapeHtml(i)}</em>`)
        .replace(/`([^`]+)`/g, (_, c) => `<code>${escapeHtml(c)}</code>`);

    const renderMarkdown = (txt) => {
        if (!txt) return '';
        const lines = escapeHtml(txt).split(/\r?\n/);
        let html = '', listType = null, listOpen = false, tableRows = [], inTable = false;

        const closeList = () => {
            if (listOpen) {
                html += listType === 'ol' ? '</ol>' : '</ul>';
                listOpen = false; listType = null;
            }
        };
        const flushTable = () => {
            if (!inTable || tableRows.length === 0) return;
            const rows = tableRows.map(r => r.replace(/^\||\|$/g, '').split('|').map(c => c.trim()));
            const header = rows[0] || [], sep = rows[1] || [], body = rows.slice(2);
            const isTbl = sep.every(c => /^:?-+:?$/.test(c));

            if (isTbl) {
                html += '<table class="message-table"><thead><tr>';
                header.forEach(c => html += `<th>${inlineFormatting(c)}</th>`);
                html += '</tr></thead><tbody>';
                body.forEach(r => {
                    html += '<tr>';
                    r.forEach(c => html += `<td>${inlineFormatting(c)}</td>`);
                    html += '</tr>';
                });
                html += '</tbody></table>';
            } else {
                tableRows.forEach(r => html += `<p>${inlineFormatting(r)}</p>`);
            }
            tableRows = []; inTable = false;
        };

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const t = line.trim();

            const heading = t.match(/^(#{1,6})\s+(.*)$/);
            if (heading) {
                closeList(); flushTable();
                const lvl = Math.min(6, heading[1].length);
                html += `<h${lvl}>${inlineFormatting(heading[2])}</h${lvl}>`;
                continue;
            }
            if (/^(---|\*\*\*|___)\s*$/.test(t)) { closeList(); flushTable(); html += '<hr class="message-hr"/>'; continue; }
            if (/^>\s?/.test(t)) { closeList(); flushTable(); html += `<blockquote>${inlineFormatting(t.replace(/^>\s?/, ''))}</blockquote>`; continue; }
            if (/^```/.test(t)) {
                closeList(); flushTable();
                let code = ''; i++;
                while (i < lines.length && !/^```/.test(lines[i].trim())) { code += lines[i] + '\n'; i++; }
                html += `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
                continue;
            }
            if (/^!\[.*\]\(.*\)$/.test(t)) {
                closeList(); flushTable();
                html += t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, a, s) =>
                    `<div class="message-image"><img src="${escapeHtml(s)}" alt="${escapeHtml(a)}"></div>`);
                continue;
            }
            if (/^\s*\|.*\|\s*$/.test(line)) { closeList(); inTable = true; tableRows.push(line); continue; }
            if (inTable && t === '') { flushTable(); continue; }
            if (/^\d+\.\s+/.test(t)) {
                flushTable();
                const txt = t.replace(/^\d+\.\s+/, '');
                if (!listOpen || listType !== 'ol') { closeList(); listType = 'ol'; listOpen = true; html += '<ol>'; }
                html += `<li>${inlineFormatting(txt)}</li>`; continue;
            }
            if (/^[-*+]\s+/.test(t)) {
                flushTable();
                const txt = t.replace(/^[-*+]\s+/, '');
                if (!listOpen || listType !== 'ul') { closeList(); listType = 'ul'; listOpen = true; html += '<ul>'; }
                html += `<li>${inlineFormatting(txt)}</li>`; continue;
            }
            if (t === '') { closeList(); flushTable(); html += '<p></p>'; continue; }

            closeList(); flushTable();
            html += `<p>${inlineFormatting(t)}</p>`;
        }
        closeList(); flushTable();
        return html;
    };

    const renderAnswer = (mini, html, cached) => {
        const box = mini.querySelector(".ai-answer");
        box.innerHTML = `
            ${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ''}
            <div class="ai-answer-content">${renderMarkdown(html)}</div>
        `;
        box.classList.remove("hidden");
    };

    // -----------------------------------------------------------------
    // 12️⃣ Ask the AI (POST)
    // -----------------------------------------------------------------
    const askAI = async (range, level) => {
        const sel = window.getSelection();
        const query = sel.toString().trim();
        if (!query) return;

        const mini = createMiniAI(range);
        const btn = mini.querySelector('.ai-get');
        const old = btn.textContent;
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
                    body: JSON.stringify({ query, level })
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
                '<em>Sorry – the AI service could not be reached.</em>', false);
        } finally {
            btn.textContent = old;
            btn.disabled = false;
        }
    };

    // -----------------------------------------------------------------
    // 13️⃣ Visual marking of the selected fragment
    // -----------------------------------------------------------------
    const markSelection = (range, level) => {
        const selected = range.toString().trim();
        if (!selected) return;
        const q = normalise(selected);
        const span = document.createElement('span');
        span.className = getHighlightClassName({
            simplified: level === 'simplified',
            technical:  level === 'technical'
        });
        span.dataset.highlightQuery = q;
        span.dataset.answer = buildAnswerText(q);
        span.appendChild(range.extractContents());
        attachHighlightEvents(span, q);
        range.insertNode(span);
    };

    // -----------------------------------------------------------------
    // 14️⃣ Bind selection → mini‑AI widget
    // -----------------------------------------------------------------
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

        // close history pop‑over if click is outside
        if (historyPopover && !historyPopover.hidden &&
            !historyPopover.contains(e.target) &&
            !historyToggle?.contains(e.target)) {
            closeHistoryPopover();
        }

        // ignore clicks inside toolbar or an already‑open mini‑widget
        if (toolbar.contains(e.target) || (mini && mini.contains(e.target))) return;

        if (!txt || !isSelectionWithinContent(sel)) {
            if (mini) mini.remove();
            mini = null;
            toolbar.style.display = 'none';
            return;
        }

        // hide the (now‑unused) toolbar
        toolbar.style.display = 'none';

        const range = sel.getRangeAt(0);
        if (mini) mini.remove();
        mini = createMiniAI(range);

        const levelSelect = mini.querySelector('.ai-level');
        const getBtn = mini.querySelector('.ai-get');
        getBtn.addEventListener('click', (ev) => {
            ev.preventDefault();
            const lvl = levelSelect.value;   // "simplified" | "technical"
            askAI(range, lvl);
        });
    };

    // -----------------------------------------------------------------
    // 15️⃣ Pre‑load cached highlights *and* populate the history UI
    // -----------------------------------------------------------------
    const preloadExistingHighlights = async () => {
        try {
            const resp = await fetch(`/slm/api/modules/${moduleId}/highlight/`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();          // {answers:[{query, answer:{simplified?,technical?}}]}

            (data.answers || []).forEach(item => {
                const query = (item.query || '').trim();
                if (!query) return;

                const ans = item.answer || {};
                const hasS = !!ans.simplified;
                const hasT = !!ans.technical;

                // Store the answers + state
                if (hasS) {
                    setHighlightAnswer(query, 'simplified', ans.simplified);
                    addHistoryEntry(query, 'simplified');
                }
                if (hasT) {
                    setHighlightAnswer(query, 'technical', ans.technical);
                    addHistoryEntry(query, 'technical');
                }

                // Apply the visual underline/wrap for the query
                applyHighlightToQuery(query, { simplified: hasS, technical: hasT });
            });

            // Ensure all spans have the right class / listeners
            syncHighlightSpans();
        } catch (e) {
            console.warn('Could not preload highlights:', e);
        }
    };

    // -----------------------------------------------------------------
    // Initialise everything
    // -----------------------------------------------------------------
    preloadExistingHighlights();   // fills maps, creates spans, populates history
    updateHistoryUI();             // (in case nothing was cached)

    if (historyToggle) {
        historyToggle.addEventListener('click', (ev) => {
            ev.stopPropagation();
            toggleHistoryPopover();
        });
    }

<<<<<<< HEAD
    document.addEventListener("mouseup", onSelectionDone);
    document.addEventListener('click', (event) => {
        if (!historyPopover || historyPopover.hidden) return;
        if (!historyPopover.contains(event.target) && !historyToggle?.contains(event.target)) {
            closeHistoryPopover();
        }
    });
    document.addEventListener("scroll", removeTooltip, true);
    document.addEventListener("mousedown", (e) => {
        if (activeTooltip && !activeTooltip.contains(e.target)) {
            removeTooltip();
        }
    });
    document.addEventListener("touchend", (e) => setTimeout(() => onSelectionDone(e), 10));
    document.addEventListener("selectionchange", () => {
=======
    // -----------------------------------------------------------------
    // Mouse / touch handling (same as before)
    // -----------------------------------------------------------------
    document.addEventListener('mouseup', onSelectionDone);
    document.addEventListener('touchend', (e) => setTimeout(() => onSelectionDone(e), 10));

    document.addEventListener('selectionchange', () => {
>>>>>>> f1da08b (highlighting less buggy v2 (needs refactoring))
        const sel = window.getSelection();
        if (!sel || !sel.toString().trim() || !isSelectionWithinContent(sel)) {
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
        if (activeTooltip && !activeTooltip.contains(e.target)) removeTooltip();
    });
}
