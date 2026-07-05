/* ------------------------------------------------------------------
   helper.js – handles:
   • submitting a question via fetch()
   • appending AI/user bubbles to the chat window
   • loading a history item back into the input box
   ------------------------------------------------------------------ */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    const levelSelect = document.getElementById("explanation-level");
    const chatWindow = document.getElementById("chat-window");
    const historyItems = document.querySelectorAll(".history-item");

    // ----------------------------------------------------------------
    // 1️⃣ Click a past query → fill the input box
    // ----------------------------------------------------------------
    historyItems.forEach(item => {
        item.addEventListener("click", () => {
            // Highlight the selected item
            historyItems.forEach(i => i.classList.remove("active"));
            item.classList.add("active");

            input.value = item.dataset.question;
            input.focus();
        });
    });

    // ----------------------------------------------------------------
    // 2️⃣ Submit a new question
    // ----------------------------------------------------------------
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const question = input.value.trim();
        if (!question) return;

        const level = levelSelect.value;

        // ---- 2a) Optimistically append the USER bubble
        appendMessage("user", question);
        input.value = "";
        input.disabled = true;          // avoid double‑clicks
        levelSelect.disabled = true;

        // ---- 2b) Call the **real** API endpoint (URL is provided by the template)
        try {
            const resp = await fetch(
                AI_HELPER_API_URL,                 // ← now a real URL
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken")
                    },
                    body: JSON.stringify({
                        question: question,
                        explanation_level: level
                    })
                }
            );

            const data = await resp.json();
            if (resp.ok && data.answer) {
                appendMessage("ai", data.answer);
                // Update the sidebar with the new user query
                addHistoryItem(question);
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
    // Helper: create a message bubble & scroll into view
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
    // Helper: push a new entry to the left‑hand history list
    // ----------------------------------------------------------------
    function addHistoryItem(question) {
        const ul = document.querySelector(".history-list");
        const li = document.createElement("li");
        li.className = "history-item";
        li.dataset.question = question;
        li.innerHTML = `<i class="fa-solid fa-user"></i>${question.substring(0,30)}`;
        ul.appendChild(li);

        // Wire the click‑handler (same as on page load)
        li.addEventListener("click", () => {
            historyItems.forEach(i => i.classList.remove("active"));
            li.classList.add("active");
            input.value = question;
            input.focus();
        });
    }

    // ----------------------------------------------------------------
    // Helper: read Django CSRF token from cookie (required for POST)
    // ----------------------------------------------------------------
    function getCookie(name) {
        const cookieValue = document.cookie
            .split("; ")
            .find(row => row.startsWith(name + "="))
            ?.split("=")[1];
        return cookieValue ? decodeURIComponent(cookieValue) : "";
    }
});
