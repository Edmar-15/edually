/* ------------------------------------------------------------------
   ai-helper.js – enhanced to work with *conversations*.
   Features:
   • Load the conversation list (mini‑map) on page load.
   • Click a conversation → fetch its messages and display.
   • When sending a question, include the active conversation_id.
   • If no conversation yet, the server creates one & returns its id.
   • Mini‑map progress bar updates on scroll.
   ------------------------------------------------------------------ */

document.addEventListener("DOMContentLoaded", () => {
    // ----------------------------------------------------------------
    // 0️⃣ ELEMENTS
    // ----------------------------------------------------------------
    const form        = document.getElementById("chat-form");
    const input       = document.getElementById("chat-input");
    const levelSelect = document.getElementById("explanation-level");
    const chatWindow  = document.getElementById("chat-window");
    const convListEl  = document.getElementById("conversation-list");

    // Tracks which conversation we are currently viewing.
    let activeConversationId = null;

    // ----------------------------------------------------------------
    // 1️⃣ Load the *mini‑map* (list of conversations) from the server.
    // ----------------------------------------------------------------
    async function loadConversationList() {
        try {
            const resp = await fetch(LIST_CONV_URL, { credentials: "same-origin" });
            const data = await resp.json();
            renderConversationList(data.conversations);
        } catch (e) {
            console.error("Failed to load conversation list:", e);
        }
    }

    function renderConversationList(conversations) {
        convListEl.innerHTML = "";

        if (conversations.length === 0) {
            convListEl.innerHTML = `<li class="conversation-empty">No conversations yet.</li>`;
            return;
        }

        conversations.forEach(c => {
            const li = document.createElement("li");
            li.className = "conversation-item";
            li.dataset.id = c.id;
            li.dataset.title = c.title;
            li.innerHTML = `<i class="fa-solid fa-comments"></i>${c.title.substring(0,30)}`;
            if (c.id == activeConversationId) li.classList.add("active");
            li.addEventListener("click", () => selectConversation(c.id));
            convListEl.appendChild(li);
        });
    }

    // ----------------------------------------------------------------
    // 2️⃣ Click a conversation → fetch its messages.
    // ----------------------------------------------------------------
    async function selectConversation(convId) {
        document.querySelectorAll(".conversation-item")
                .forEach(i => i.classList.remove("active"));
        const clicked = document.querySelector(`.conversation-item[data-id="${convId}"]`);
        if (clicked) clicked.classList.add("active");

        activeConversationId = convId;
        chatWindow.innerHTML = "";          // clear old messages
        input.value = "";
        input.disabled = true;
        levelSelect.disabled = true;

        try {
            const url = GET_CONV_URL + convId + "/";
            const resp = await fetch(url, { credentials: "same-origin" });
            const data = await resp.json();

            data.messages.forEach(m => appendMessage(m.role, m.content));
        } catch (e) {
            console.error("Failed to load conversation:", e);
        } finally {
            input.disabled = false;
            levelSelect.disabled = false;
            input.focus();
        }
    }

    // ----------------------------------------------------------------
    // 3️⃣ Submit a new question
    // ----------------------------------------------------------------
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const question = input.value.trim();
        if (!question) return;

        const level = levelSelect.value;

        // Optimistic UI
        appendMessage("user", question);
        input.value = "";
        input.disabled = true;
        levelSelect.disabled = true;

        const payload = {
            question,
            explanation_level: level,
            conversation_id: activeConversationId,   // may be null
        };

        try {
            const resp = await fetch(AI_HELPER_API_URL, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken")
                },
                body: JSON.stringify(payload)
            });

            const data = await resp.json();

            if (resp.ok && data.answer) {
                appendMessage("ai", data.answer);

                // Server might have created a new conversation – keep UI in sync
                if (!activeConversationId || activeConversationId != data.conversation_id) {
                    activeConversationId = data.conversation_id;
                    await loadConversationList();
                }

                // Highlight the active conversation in the list
                document.querySelectorAll(".conversation-item")
                        .forEach(i => i.classList.remove("active"));
                const activeEl = document.querySelector(`.conversation-item[data-id="${activeConversationId}"]`);
                if (activeEl) activeEl.classList.add("active");
            } else {
                console.error("API error:", data);
                appendMessage("ai", "Sorry – something went wrong.");
            }
        } catch (err) {
            console.error(err);
            appendMessage("ai", "Network error – try again later.");
        } finally {
            input.disabled = false;
            levelSelect.disabled = false;
            input.focus();
        }
    });

    // ----------------------------------------------------------------
    // 4️⃣ Helper: create a message bubble & scroll into view
    // ----------------------------------------------------------------
    function appendMessage(role, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}-message`;

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = role === "ai" ? "AI" : "You";

        const body = document.createElement("div");
        body.className = "message-body";

        const author = document.createElement("p");
        author.className = "message-author";
        author.textContent = role === "ai" ? "EduAlly" : "Student";

        const txt = document.createElement("p");
        txt.className = "message-text";
        txt.textContent = text;

        body.append(author, txt);
        msgDiv.append(avatar, body);
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // ----------------------------------------------------------------
    // 5️⃣ Helper: read Django CSRF token from cookie (required for POST)
    // ----------------------------------------------------------------
    function getCookie(name) {
        const cookieValue = document.cookie
            .split("; ")
            .find(row => row.startsWith(name + "="))
            ?.split("=")[1];
        return cookieValue ? decodeURIComponent(cookieValue) : "";
    }

    // ----------------------------------------------------------------
    // 6️⃣ Mini‑map progress bar – update on scroll
    // ----------------------------------------------------------------
    function initMiniMap() {
        const bar = chatWindow.querySelector(".message-minimap .progress");
        if (!bar) return;

        const update = () => {
            const scrollTop = chatWindow.scrollTop;
            const maxScroll = chatWindow.scrollHeight - chatWindow.clientHeight;
            const pct = maxScroll ? (scrollTop / maxScroll) * 100 : 0;
            bar.style.width = `${pct}%`;
        };
        chatWindow.addEventListener("scroll", update);
        // initialise once (e.g. when messages are first rendered)
        update();
    }

    // ----------------------------------------------------------------
    // 7️⃣ Initialise page: load conversation list, then (if any)
    //     load the conversation that Django rendered as the “active” one.
    // ----------------------------------------------------------------
    (async () => {
        await loadConversationList();

        const qs = new URLSearchParams(window.location.search);
        const startId = qs.get("conversation_id");
        if (startId) {
            await selectConversation(startId);
        }
        // After everything is in the DOM, start the mini‑map listener.
        initMiniMap();
    })();

});
