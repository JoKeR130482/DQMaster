document.addEventListener('DOMContentLoaded', () => {

    // --- 1. STATE MANAGEMENT ---
    const state = {
        words: [],
        isLoading: true,
        searchTerm: '',
        sortDirection: 'asc',
    };

    // --- 2. DOM ELEMENTS ---
    const dom = {
        loadingSpinner: document.getElementById('loading'),
        errorContainer: document.getElementById('error-container'),
        dictionaryContainer: document.getElementById('dictionary-container'),
        dictionaryTableBody: document.getElementById('dictionary-table-body'),
        searchInput: document.getElementById('search-input'),
        sortWordBtn: document.getElementById('sort-word-btn'),
        emptyState: document.getElementById('empty-state'),
    };

    // --- 3. API HELPERS ---
    const api = {
        getDictionary: () => fetch('/api/dictionary'),
    };

    // --- 5. RENDER FUNCTIONS ---
    function render() {
        dom.loadingSpinner.style.display = state.isLoading ? 'block' : 'none';

        const filteredAndSortedWords = getFilteredAndSortedWords();
        dom.dictionaryTableBody.innerHTML = '';

        if (filteredAndSortedWords.length > 0) {
            dom.dictionaryContainer.style.display = 'block';
            dom.emptyState.style.display = 'none';
            filteredAndSortedWords.forEach(word => {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${word}</td>`;
                dom.dictionaryTableBody.appendChild(row);
            });
        } else {
            dom.dictionaryContainer.style.display = 'none';
            dom.emptyState.style.display = 'block';
        }
        lucide.createIcons();
    }

    function getFilteredAndSortedWords() {
        let words = state.words.filter(word =>
            word.toLowerCase().includes(state.searchTerm.toLowerCase())
        );

        words.sort((a, b) => {
            const dir = state.sortDirection === 'asc' ? 1 : -1;
            return a.localeCompare(b, 'ru') * dir;
        });

        return words;
    }

    // --- 6. EVENT HANDLERS & LOGIC ---
    function setupEventListeners() {
        dom.searchInput.addEventListener('input', (e) => {
            state.searchTerm = e.target.value;
            render();
        });

        dom.sortWordBtn.addEventListener('click', () => {
            state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
            render();
        });
    }

    // --- 7. INITIALIZATION ---
    async function init() {
        state.isLoading = true;
        render();
        try {
            const response = await api.getDictionary();
            if (!response.ok) throw new Error('Failed to fetch dictionary');
            state.words = await response.json();
        } catch (error) {
            dom.errorContainer.textContent = "Не удалось загрузить словарь.";
            dom.errorContainer.style.display = "block";
        } finally {
            state.isLoading = false;
            render();
        }
    }

    setupEventListeners();
    init();
});