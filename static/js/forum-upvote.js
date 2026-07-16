/**
 * Forum AJAX Upvote Handler
 * Handles upvoting for both posts and replies using AJAX
 */

document.addEventListener('DOMContentLoaded', function() {
    const getCsrfToken = () => {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    const handleUpvoteResponse = (button, data, countSelector) => {
        if (!data.success) return;

        let countSpan = button.querySelector(countSelector);
        if (!countSpan) {
            countSpan = button.closest('.side-upvote')?.querySelector('.upvote-num');
        }
        if (countSpan) {
            countSpan.textContent = data.upvotes;
        }

        if (data.has_upvoted) {
            button.classList.add('has-upvoted');
        } else {
            button.classList.remove('has-upvoted');
        }
    };

    document.body.addEventListener('click', async function(e) {
        const postButton = e.target.closest('.upvote-btn');
        if (postButton) {
            e.preventDefault();
            const endpoint = postButton.dataset.endpoint;
            if (!endpoint) return;

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                });
                if (!response.ok) {
                    console.error('Upvote failed:', response.status);
                    return;
                }
                const data = await response.json();
                handleUpvoteResponse(postButton, data, '.upvote-count');
            } catch (error) {
                console.error('Error:', error);
            }
            return;
        }

        const replyButton = e.target.closest('.reply-upvote-btn');
        if (replyButton) {
            e.preventDefault();
            const endpoint = replyButton.dataset.endpoint;
            if (!endpoint) return;

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                });
                if (!response.ok) {
                    console.error('Upvote failed:', response.status);
                    return;
                }
                const data = await response.json();
                handleUpvoteResponse(replyButton, data, '.reply-upvote-count');
            } catch (error) {
                console.error('Error:', error);
            }
        }
    });
});
