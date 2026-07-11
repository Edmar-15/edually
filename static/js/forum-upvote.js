/**
 * Forum AJAX Upvote Handler
 * Handles upvoting for both posts and replies using AJAX
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get CSRF token from cookie
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

    // Handle post upvotes
    document.querySelectorAll('.upvote-btn').forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const postId = this.dataset.postId;
            const endpoint = this.dataset.endpoint;
            const csrfToken = getCsrfToken();
            
            if (!endpoint) return;

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json',
                    },
                });

                if (!response.ok) {
                    console.error('Upvote failed:', response.status);
                    return;
                }

                const data = await response.json();
                
                if (data.success) {
                    // Update upvote count
                    const countSpan = this.querySelector('.upvote-count');
                    if (countSpan) {
                        countSpan.textContent = data.upvotes;
                    }

                    // Update button styling based on upvoted status
                    if (data.has_upvoted) {
                        this.classList.add('has-upvoted');
                    } else {
                        this.classList.remove('has-upvoted');
                    }
                }
            } catch (error) {
                console.error('Error:', error);
            }
        });
    });

    // Handle reply upvotes
    document.querySelectorAll('.reply-upvote-btn').forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const replyId = this.dataset.replyId;
            const endpoint = this.dataset.endpoint;
            const csrfToken = getCsrfToken();
            
            if (!endpoint) return;

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json',
                    },
                });

                if (!response.ok) {
                    console.error('Upvote failed:', response.status);
                    return;
                }

                const data = await response.json();
                
                if (data.success) {
                    // Update upvote count
                    const countSpan = this.querySelector('.reply-upvote-count');
                    if (countSpan) {
                        countSpan.textContent = data.upvotes;
                    }

                    // Update button styling based on upvoted status
                    if (data.has_upvoted) {
                        this.classList.add('has-upvoted');
                    } else {
                        this.classList.remove('has-upvoted');
                    }
                }
            } catch (error) {
                console.error('Error:', error);
            }
        });
    });
});
