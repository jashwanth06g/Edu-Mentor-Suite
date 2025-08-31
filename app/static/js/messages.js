// mentor_connect_ngo_enhanced/app/static/js/messages.js

document.addEventListener('DOMContentLoaded', function() {
    const messageList = document.getElementById('message-list');
    const messageForm = document.querySelector('#messages-container form'); // Assuming form is within messages.html

    // Function to scroll to the bottom of the message list
    function scrollToBottom() {
        messageList.scrollTop = messageList.scrollHeight;
    }

    // Function to fetch and display messages
    let lastMessageCount = 0;
    function fetchMessages() {
        // 'fetchMessagesUrl' and 'currentUserId' are passed from the Jinja template in messages.html
        fetch(fetchMessagesUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(messages => {
                // Only update if message count has changed
                if (messages.length > lastMessageCount) {
                    messageList.innerHTML = ''; // Clear existing messages
                    messages.forEach(msg => {
                        const messageDiv = document.createElement('div');
                        messageDiv.classList.add('d-flex', 'mb-2');

                        if (msg.is_current_user_sender) {
                            messageDiv.classList.add('justify-content-end');
                            messageDiv.innerHTML = `
                                <div class="card bg-primary text-white p-2" style="max-width: 75%;">
                                    <div class="card-subtitle mb-1 text-white-50">
                                        <small>You <span class="ms-2">${msg.timestamp.substring(11, 16)}</span></small>
                                    </div>
                                    <p class="card-text mb-0">${msg.content}</p>
                                </div>
                            `;
                        } else {
                            messageDiv.classList.add('justify-content-start');
                            messageDiv.innerHTML = `
                                <div class="card bg-light p-2" style="max-width: 75%;">
                                    <div class="card-subtitle mb-1 text-muted">
                                        <small>${msg.sender_username} <span class="ms-2">${msg.timestamp.substring(11, 16)}</span></small>
                                    </div>
                                    <p class="card-text mb-0">${msg.content}</p>
                                </div>
                            `;
                        }
                        messageList.appendChild(messageDiv);
                    });
                    scrollToBottom(); // Scroll to bottom after new messages
                    lastMessageCount = messages.length;
                }
            })
            .catch(error => {
                console.error('Error fetching messages:', error);
            });
    }

    // Scroll to bottom on initial load
    scrollToBottom();

    // Poll for new messages every 3 seconds
    setInterval(fetchMessages, 3000);

    // Optional: Clear message input after sending
    // You might want to handle form submission via AJAX for a smoother experience
    // For now, it relies on full page reload after Flask handles form submission
    // if (messageForm) {
    //     messageForm.addEventListener('submit', function() {
    //         setTimeout(() => {
    //             document.getElementById('content').value = ''; // Assuming your message textarea has id 'content'
    //             scrollToBottom();
    //         }, 100); // Small delay to allow Flask redirect to happen
    //     });
    // }
});

