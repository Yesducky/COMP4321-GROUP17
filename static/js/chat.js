const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const clearChatBtn = document.getElementById('clear-chat');

// Configure marked.js options
marked.setOptions({
    breaks: true,         // Enable line breaks
    gfm: true,            // Enable GitHub Flavored Markdown
    headerIds: false,     // Disable header IDs
    mangle: false,        // Disable mangling to prevent escaping of certain characters
    sanitize: false       // Allow HTML (sanitize manually if needed)
});

function appendMessage(sender, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = sender === 'user' ? 'flex justify-end' : 'flex justify-start';
    const bubble = document.createElement('span');

    if (sender === 'user') {
        bubble.className = 'inline-block px-4 py-2 rounded-2xl shadow transition-all duration-200 max-w-[80%] break-words bg-[#003366] text-white rounded-br-md animate-bounce-in-right';
        bubble.textContent = text;
    } else {
        bubble.className = 'inline-block px-4 py-2 rounded-2xl shadow transition-all duration-200 max-w-[80%] break-words bg-gray-200 text-gray-900 rounded-bl-md animate-bounce-in-left markdown-bubble';

        // Process markdown for bot messages
        try {
            bubble.innerHTML = marked.parse(text);
        } catch (e) {
            // Fallback to basic formatting if marked fails
            bubble.innerHTML = text
                .replace(/\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        }
    }

    msgDiv.appendChild(bubble);
    chatWindow.appendChild(msgDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

// Welcome message
window.addEventListener('DOMContentLoaded', () => {
    appendMessage('bot', 'Ask me anything about the project. Try:\n ***Summarize the PG program of HKUST***\n***What opportunities are available for UG students?***');
});

clearChatBtn.addEventListener('click', function() {
    chatWindow.innerHTML = '';
    appendMessage('bot', '**Chat cleared.**');
});

chatForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;
    appendMessage('user', message);
    userInput.value = '';

    // Loading indicator
    const loadingMsgDiv = document.createElement('div');
    loadingMsgDiv.className = 'flex justify-start';
    const loadingBubble = document.createElement('span');
    loadingBubble.className = 'inline-block px-4 py-2 rounded-2xl shadow transition-all duration-200 max-w-[80%] break-words bg-gray-200 text-gray-900 rounded-bl-md animate-bounce-in-left';
    loadingBubble.innerHTML = '<span class="italic text-gray-400">Responding...</span>';
    loadingMsgDiv.appendChild(loadingBubble);
    chatWindow.appendChild(loadingMsgDiv);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });

        // Remove loading message
        chatWindow.removeChild(loadingMsgDiv);

        if (response.ok) {
            const data = await response.json();
            appendMessage('bot', data.reply);
        } else {
            appendMessage('bot', 'Sorry, there was an error processing your request.');
        }
    } catch (error) {
        chatWindow.removeChild(loadingMsgDiv);
        appendMessage('bot', `Sorry, an error occurred: ${error.message}`);
    }
});