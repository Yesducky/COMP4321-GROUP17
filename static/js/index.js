function validateForm() {
    const query = document.getElementById('search-query').value.trim();
    if (!query) {
        return false;
    }

    saveQueryToHistory(query);
    return true;
}

function saveQueryToHistory(query) {
    // Get existing history or create empty array
    let history = JSON.parse(localStorage.getItem('searchHistory') || '[]');

    // Remove duplicates of this query
    history = history.filter(item => item.query !== query);

    // Add new query at the beginning with timestamp
    history.unshift({
        query: query,
        timestamp: new Date().toISOString()
    });

    // Keep only latest 10 queries
    if (history.length > 10) {
        history = history.slice(0, 10);
    }

    // Save back to localStorage
    localStorage.setItem('searchHistory', JSON.stringify(history));
}

function showQueryHistory() {
    const history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
    const historyElement = document.getElementById('history-items');
    historyElement.innerHTML = '';

    if (history.length === 0) {
        historyElement.innerHTML = '<div class="p-3 text-center text-gray-500">No search history</div>';
    } else {
        history.forEach(item => {
            const date = new Date(item.timestamp);
            const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;

            const historyItem = document.createElement('div');
            historyItem.className = 'p-3 border-b border-gray-100 hover:bg-gray-50 cursor-pointer flex justify-between';
            historyItem.innerHTML = `
                <span class="font-medium">${item.query}</span>
                <span class="text-xs text-gray-500">${formattedDate}</span>
            `;
            historyItem.addEventListener('click', () => {
                document.getElementById('search-query').value = item.query;
                document.querySelector('form').submit();
            });
            historyElement.appendChild(historyItem);
        });
    }

    document.getElementById('query-history').classList.remove('hidden');
}

// Document ready function
document.addEventListener('DOMContentLoaded', () => {
    // Hide history when clicking outside
    document.addEventListener('click', (e) => {
        const historyElement = document.getElementById('query-history');
        const searchInput = document.getElementById('search-query');

        if (e.target !== searchInput && historyElement && !historyElement.contains(e.target)) {
            historyElement.classList.add('hidden');
        }
    });

    // Clear history functionality
    const clearHistoryBtn = document.getElementById('clear-history');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            localStorage.removeItem('searchHistory');
            document.getElementById('history-items').innerHTML =
                '<div class="p-3 text-center text-gray-500">No search history</div>';
        });
    }

    // Add focus event to search query input
    const searchInput = document.getElementById('search-query');
    if (searchInput) {
        searchInput.addEventListener('focus', showQueryHistory);
    }
});