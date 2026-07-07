// static/js/slm/highlight_ai.js
import { csrftoken } from "./utils.js";

/**
 * Initialise the highlight‑→‑Ask‑AI behaviour.
 *
 * @param {HTMLElement} toolbar   – the floating toolbar that already exists
 *                                 (it will be hidden after a selection).
 * @param {number} moduleId        – PK of the current Module.
 */
export function initHighlightAI(toolbar, moduleId) {
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

        return mini;
    };

    const renderAnswer = (mini, html, cached) => {
        const box = mini.querySelector(".ai-answer");
        box.innerHTML = `
            ${cached ? '<span class="ai-cached">🗃️ Cached answer</span>' : ''}
            ${html}
        `;
        box.classList.remove("hidden");
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
            markSelection(range);
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
    const markSelection = (range) => {
        const span = document.createElement("span");
        span.className = "highlight-marked";
        span.appendChild(range.extractContents());
        range.insertNode(span);
    };

    // -----------------------------------------------------------------
    // 4️⃣  Bind selection → mini‑AI widget
    // -----------------------------------------------------------------
    let mini = null; // current widget

    const onSelectionDone = (event) => {
        const sel  = window.getSelection();
        const text = sel.toString().trim();

        // Ignore clicks inside the old toolbar or an already‑open mini.
        if (toolbar.contains(event.target) || (mini && mini.contains(event.target))) {
            return;
        }

        if (!text) {
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
    document.addEventListener("mouseup", onSelectionDone);
    document.addEventListener("touchend", (e) => setTimeout(() => onSelectionDone(e), 10));
    document.addEventListener("selectionchange", () => {
        const sel = window.getSelection();
        if (!sel || sel.toString().trim().length === 0) {
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
