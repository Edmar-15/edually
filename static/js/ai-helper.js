
document.addEventListener("DOMContentLoaded", () => {
    // Elements used by the chat UI.
    const form        = document.getElementById("chat-form");
    const input       = document.getElementById("chat-input");
    const levelSelect = document.getElementById("explanation-level");
    const chatWindow  = document.getElementById("chat-window");
    const convListEl  = document.getElementById("conversation-list");
    const emptyState  = document.querySelector(".empty-state");
    const headerBadgeText = document.getElementById("chat-header-badge-text");
    const conversationMap = document.getElementById("conversation-map");
    const conversationResizer = document.getElementById("conversation-resizer");

    // Current conversation ID.
    let activeConversationId = document.querySelector(".conversation-item.active")?.dataset.id || null;
    let messageCounter = 0;
    // Pause auto-scroll while the user reads.
    let userInteracting = false;
    let interactionTimer = null;

    function markUserInteracting() {
        userInteracting = true;
        clearTimeout(interactionTimer);
        interactionTimer = setTimeout(() => {
            userInteracting = false;
        }, 1800);
    }
    // Auto-scroll only when the user is near the bottom.
    function isUserNearBottom() {
        const threshold = 140; // pixels from bottom considered "near"
        return (chatWindow.scrollHeight - chatWindow.clientHeight - chatWindow.scrollTop) < threshold;
    }

    // Load conversations.
    async function loadConversationList() {
        try {
            const resp = await fetch(LIST_CONV_URL, { credentials: "same-origin" });
            const data = await resp.json();
            renderConversationList(data.conversations);
        } catch (e) {
            console.error("Failed to load conversation list:", e);
        }
    }

    function toggleEmptyState(show) {
        if (emptyState) {
            emptyState.classList.toggle("hidden", !show);
        }
    }

    function updateHeaderBadge(title) {
        if (headerBadgeText) {
            const label = title && title.trim() ? title.trim() : "New conversation";
            headerBadgeText.textContent = label.length > 40 ? `${label.slice(0, 37)}...` : label;
        }
    }


    [ 'scroll', 'wheel', 'touchstart', 'pointerdown' ].forEach(ev => {
        chatWindow.addEventListener(ev, markUserInteracting, { passive: true });
    });

    let isResizing = false;
    let startX = 0;
    let startWidth = 260;

    if (conversationResizer && conversationMap) {
        conversationResizer.addEventListener('mousedown', (event) => {
            isResizing = true;
            startX = event.clientX;
            startWidth = conversationMap.getBoundingClientRect().width;
            conversationResizer.classList.add('dragging');
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
            event.preventDefault();
        });

        document.addEventListener('mousemove', (event) => {
            if (!isResizing) return;
            const delta = event.clientX - startX;
            const nextWidth = Math.max(72, Math.min(360, startWidth - delta));
            document.documentElement.style.setProperty('--conversation-width', `${nextWidth}px`);
            conversationMap.classList.toggle('is-collapsed', nextWidth <= 100);
        });

        document.addEventListener('mouseup', () => {
            if (!isResizing) return;
            isResizing = false;
            conversationResizer.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        });
    }

    // Toggle the minimap popup.
    const minimapToggle = document.getElementById('minimap-toggle');
    const minimapPopup = document.getElementById('minimap-popup');
    if (minimapToggle && minimapPopup) {
        minimapToggle.addEventListener('click', (e) => {
            const visible = !minimapPopup.classList.contains('hidden');
            if (visible) {
                minimapPopup.classList.add('hidden');
                minimapToggle.setAttribute('aria-expanded', 'false');
            } else {
                minimapPopup.classList.remove('hidden');
                minimapToggle.setAttribute('aria-expanded', 'true');
            }
        });

        // Close the popup when clicking outside.
        document.addEventListener('click', (ev) => {
            if (!minimapPopup.classList.contains('hidden')) {
                if (!minimapPopup.contains(ev.target) && !minimapToggle.contains(ev.target)) {
                    minimapPopup.classList.add('hidden');
                    minimapToggle.setAttribute('aria-expanded', 'false');
                }
            }
        });
    }

    function scrollToPromptMessage(promptText) {
        const normalized = promptText.trim().replace(/\s+/g, ' ').toLowerCase();
        const candidates = Array.from(chatWindow.querySelectorAll('.message.user-message'));

        const directMatch = candidates.find((messageEl) => {
            const text = (messageEl.querySelector('.message-text')?.textContent || '').trim().replace(/\s+/g, ' ').toLowerCase();
            return text === normalized;
        });

        const fallbackMatch = directMatch || candidates.find((messageEl) => {
            const text = (messageEl.querySelector('.message-text')?.textContent || '').trim().replace(/\s+/g, ' ').toLowerCase();
            return text.includes(normalized) || normalized.includes(text);
        });

        const target = fallbackMatch || candidates[0];
        if (!target) return;

        target.classList.add('message-targeted');
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(() => target.classList.remove('message-targeted'), 1600);
    }

    function addMessageAnimation(messageEl) {
        messageEl.animate([
            { opacity: 0, transform: 'translateY(8px)' },
            { opacity: 1, transform: 'translateY(0)' }
        ], {
            duration: 220,
            easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
            fill: 'forwards'
        });
    }

    function renderPromptHistory(messages, conversationId) {
        const miniList = document.getElementById('minimap-list');
        if (!miniList) return;

        miniList.innerHTML = '';

        const prompts = (messages || [])
            .filter(message => message.role === 'user' && message.content && message.content.trim())
            .map(message => message.content.trim());

        if (prompts.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.className = 'conversation-empty';
            emptyItem.textContent = 'No prompt history yet.';
            miniList.appendChild(emptyItem);
            return;
        }

        prompts.forEach((prompt) => {
            const displayText = prompt.replace(/\s+/g, ' ').slice(0, 80);
            const item = document.createElement('li');
            item.dataset.id = conversationId;
            item.textContent = displayText.length < prompt.length ? `${displayText}…` : displayText;
            item.addEventListener('click', () => scrollToPromptMessage(prompt));
            miniList.appendChild(item);
        });
    }

    function renderConversationList(conversations) {
        convListEl.innerHTML = "";

        if (conversations.length === 0) {
            convListEl.innerHTML = `<li class="conversation-empty">No conversations yet.</li>`;
        } else {
            conversations.forEach(c => {
                const prompt = (c.prompt || c.title || "Conversation").toString().trim();
                const displayText = prompt.replace(/\s+/g, " ").slice(0, 60);
                const li = document.createElement("li");
                li.className = "conversation-item";
                li.dataset.id = c.id;
                li.dataset.title = prompt;

                const text = document.createElement("span");
                text.textContent = displayText.length < prompt.length ? `${displayText}…` : displayText;

                li.appendChild(text);
                if (c.id == activeConversationId) li.classList.add("active");
                li.addEventListener("click", () => selectConversation(c.id));
                convListEl.appendChild(li);
            });
        }
    }

    // Load a selected conversation.
    async function selectConversation(convId) {
        document.querySelectorAll(".conversation-item")
                .forEach(i => i.classList.remove("active"));
        messageCounter = 0;
        const clicked = document.querySelector(`.conversation-item[data-id="${convId}"]`);
        if (clicked) clicked.classList.add("active");

        activeConversationId = convId;
        document.querySelectorAll(".message").forEach((message) => message.remove());
        updateHeaderBadge(document.querySelector(`.conversation-item[data-id="${convId}"]`)?.dataset.title || "New conversation");
        input.value = "";
        input.disabled = true;
        levelSelect.disabled = true;
        toggleEmptyState(false);

        try {
            const url = GET_CONV_URL + convId + "/";
            const resp = await fetch(url, { credentials: "same-origin" });
            const data = await resp.json();

            if (data.messages && data.messages.length) {
                data.messages.forEach(m => appendMessage(m.role, m.content));
                renderPromptHistory(data.messages, convId);
                toggleEmptyState(false);
            } else {
                renderPromptHistory([], convId);
                toggleEmptyState(true);
            }
        } catch (e) {
            console.error("Failed to load conversation:", e);
        } finally {
            input.disabled = false;
            levelSelect.disabled = false;
            input.focus();
        }
    }

    // Submit a new question.
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const question = input.value.trim();
        if (!question) return;

        const level = levelSelect.value;

        // Optimistic UI
        toggleEmptyState(false);
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
            showTypingIndicator(true);
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
                appendMessage("ai", data.answer, true);

                // Server might have created a new conversation – keep UI in sync
                if (!activeConversationId || activeConversationId != data.conversation_id) {
                    activeConversationId = data.conversation_id;
                    await loadConversationList();
                }

                const promptMessages = Array.from(chatWindow.querySelectorAll('.message.user-message'))
                    .map((messageEl) => ({
                        role: 'user',
                        content: messageEl.querySelector('.message-text')?.textContent || ''
                    }));
                renderPromptHistory(promptMessages, activeConversationId);
                updateHeaderBadge(data.title || question);

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
            showTypingIndicator(false);
            input.disabled = false;
            levelSelect.disabled = false;
            input.focus();
        }
    });

    function showTypingIndicator(visible) {
        const loader = document.getElementById("chat-loading");
        if (loader) {
            loader.classList.toggle("hidden", !visible);
            if (visible) {
                // only jump if user is already near the bottom and not
                // actively interacting with the scroll (prevents fighting)
                if (isUserNearBottom() && !userInteracting) {
                    setTimeout(() => {
                        chatWindow.scrollTop = chatWindow.scrollHeight;
                    }, 10);
                }
            }
        }
    }

    function appendMessage(role, text, animate = false) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}-message`;
        msgDiv.dataset.messageIndex = messageCounter;
        messageCounter += 1;

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        if (role === "ai") {
            avatar.innerHTML = '<i class="fa-solid fa-robot"></i>';
        } else {
            avatar.textContent = "You";
        }

        const body = document.createElement("div");
        body.className = "message-body";

        const txt = document.createElement("div");
        txt.className = "message-text";

        // Show the AI label only for assistant replies.
        if (role === 'ai') {
            const author = document.createElement("p");
            author.className = "message-author";
            author.textContent = "EduAlly";
            body.append(author, txt);
        } else {
            body.append(txt);
        }
        msgDiv.append(avatar, body);

        // Keep the loader at the end of the chat.
        const loaderEl = chatWindow.querySelector("#chat-loading");
        const minimap = chatWindow.querySelector(".message-minimap");
        if (loaderEl) {
            chatWindow.insertBefore(msgDiv, loaderEl);
        } else if (minimap) {
            chatWindow.insertBefore(msgDiv, minimap);
        } else {
            chatWindow.appendChild(msgDiv);
        }

        addMessageAnimation(msgDiv);

        setTimeout(() => {
            if (isUserNearBottom() && !userInteracting) {
                chatWindow.scrollTop = chatWindow.scrollHeight;
            }
        }, 10);

        if (role === "ai" && animate) {
            animateMessageText(txt, text);
        } else {
            txt.innerHTML = renderMarkdown(text);
        }
    }

    function animateMessageText(container, fullText) {
        let index = 0;
        const speed = 18;
        const scrollEvery = 3;
        const renderEvery = 1;
        const messageEl = container.closest('.message');
        const timer = setInterval(() => {
            index += 1;
            // Render the reply as it appears.
            const snippet = fullText.slice(0, index);
            if (index % renderEvery === 0 || index === fullText.length) {
                container.innerHTML = renderMarkdown(snippet);
            } else {
                container.textContent = snippet;
            }

            // Keep the latest reply visible while typing.
            if (isUserNearBottom() && !userInteracting) {
                if (messageEl && index % scrollEvery === 0) {
                    messageEl.scrollIntoView({ behavior: 'auto', block: 'end' });
                } else {
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            }

            if (index >= fullText.length) {
                clearInterval(timer);
                container.innerHTML = renderMarkdown(fullText);
                setTimeout(() => {
                    if (isUserNearBottom() && !userInteracting) {
                        chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior: 'smooth' });
                    }
                }, 50);
            }
        }, speed);
    }

    // Render markdown safely.
    function escapeHtml(value) {
        return value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function renderMarkdown(text) {
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

            // Headings: # H1, ## H2, ### H3 ... up to H6
            const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
            if (headingMatch) {
                closeList();
                flushTable();
                const level = Math.min(6, headingMatch[1].length);
                const content = inlineFormatting(headingMatch[2]);
                html += `<h${level}>${content}</h${level}>`;
                continue;
            }

            // Horizontal rule: --- or *** or ___ on a single line
            if (/^(?:---|\*\*\*|___)\s*$/.test(trimmed)) {
                closeList();
                flushTable();
                html += "<hr class=\"message-hr\"/>";
                continue;
            }

            // Blockquote: > quoted text
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
    }

    function inlineFormatting(text) {
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
    }

    function renderExistingMessages() {
        document.querySelectorAll(".message-text").forEach((el) => {
            const raw = el.textContent || el.innerText || "";
            el.innerHTML = renderMarkdown(raw);
        });
    }

    // Read the CSRF token.
    function getCookie(name) {
        const cookieValue = document.cookie
            .split("; ")
            .find(row => row.startsWith(name + "="))
            ?.split("=")[1];
        return cookieValue ? decodeURIComponent(cookieValue) : "";
    }

    // Update the minimap progress bar.
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
        update();
    }

    // Initialize the page.
    (async () => {
        await loadConversationList();

        const qs = new URLSearchParams(window.location.search);
        const startId = qs.get("conversation_id");
        if (startId) {
            await selectConversation(startId);
        }
        renderExistingMessages();
        initMiniMap();
    })();

});
