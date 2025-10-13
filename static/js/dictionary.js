document.addEventListener('DOMContentLoaded', () => {

    // --- 1. STATE MANAGEMENT ---
    const state = {
        words: [],
        isLoading: true,
        searchTerm: '',
        sortDirection: 'asc',
        editingWord: null, // The word currently being edited
    };

    // --- 2. DOM ELEMENTS ---
    const dom = {
        loadingSpinner: document.getElementById('loading'),
        errorContainer: document.getElementById('error-container'),
        dictionaryContainer: document.getElementById('dictionary-container'),
        dictionaryTableBody: document.getElementById('dictionary-table-body'),
        searchInput: document.getElementById('search-input'),
        addWordInput: document.getElementById('new-word-input'),
        addWordBtn: document.getElementById('add-word-btn'),
        sortWordBtn: document.getElementById('sort-word-btn'),
        emptyState: document.getElementById('empty-state'),
        notificationToast: document.getElementById('notification-toast'),
    };

    // --- 3. API HELPERS ---
    const api = {
        getDictionary: () => fetch('/api/dictionary'),
        addWord: (word) => fetch('/api/dictionary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ word }),
        }),
        updateWord: (oldWord, newWord) => fetch(`/api/dictionary/${encodeURIComponent(oldWord)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_word: newWord }),
        }),
        deleteWord: (word) => fetch(`/api/dictionary/${encodeURIComponent(word)}`, {
            method: 'DELETE',
        }),
    };

    // --- 5. RENDER FUNCTIONS ---
    function render() {
        dom.loadingSpinner.style.display = state.isLoading ? 'block' : 'none';

        const filteredAndSortedWords = getFilteredAndSortedWords();
        dom.dictionaryTableBody.innerHTML = '';

        if (filteredAndSortedWords.length > 0 || state.searchTerm) {
            dom.dictionaryContainer.style.display = 'table';
            dom.emptyState.style.display = 'none';

            filteredAndSortedWords.forEach(word => {
                const row = document.createElement('tr');
                row.dataset.word = word;

                if (state.editingWord === word) {
                    row.innerHTML = `
                        <td class="word-cell">
                            <input type="text" class="edit-word-input" value="${word}">
                        </td>
                        <td class="actions-cell">
                            <button class="btn btn-icon save-edit-btn" title="Сохранить"><i data-lucide="check"></i></button>
                            <button class="btn btn-icon cancel-edit-btn" title="Отмена"><i data-lucide="x"></i></button>
                        </td>
                    `;
                } else {
                    row.innerHTML = `
                        <td class="word-cell">${word}</td>
                        <td class="actions-cell">
                            <button class="btn btn-icon edit-word-btn" title="Редактировать"><i data-lucide="pencil"></i></button>
                            <button class="btn btn-icon danger delete-word-btn" title="Удалить"><i data-lucide="trash-2"></i></button>
                        </td>
                    `;
                }
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

    // --- 4. UTILS ---
    const showNotification = (message, type = 'success') => {
        dom.notificationToast.textContent = message;
        dom.notificationToast.className = `toast ${type} show`;
        setTimeout(() => { dom.notificationToast.className = dom.notificationToast.className.replace('show', ''); }, 3000);
    };

    // --- 6. EVENT HANDLERS & LOGIC ---
    async function handleAddWord() {
        const newWord = dom.addWordInput.value.trim();
        if (!newWord) return;

        try {
            const response = await api.addWord(newWord);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to add word');
            }
            showNotification(`Слово "${newWord}" успешно добавлено.`, 'success');
            dom.addWordInput.value = '';
            await init(); // Re-fetch all words
        } catch (error) {
            showNotification(`Ошибка: ${error.message}`, 'error');
        }
    }

    async function handleDeleteWord(word) {
        if (!confirm(`Вы уверены, что хотите удалить слово "${word}"?`)) return;

        try {
            const response = await api.deleteWord(word);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to delete word');
            }
            showNotification(`Слово "${word}" удалено.`, 'success');
            await init();
        } catch (error) {
            showNotification(`Ошибка: ${error.message}`, 'error');
        }
    }

    async function handleUpdateWord(oldWord, newWord) {
        if (!newWord || oldWord === newWord) {
            state.editingWord = null;
            render();
            return;
        }

        try {
            const response = await api.updateWord(oldWord, newWord);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to update word');
            }
            showNotification(`Слово "${oldWord}" обновлено на "${newWord}".`, 'success');
            state.editingWord = null;
            await init();
        } catch (error) {
            showNotification(`Ошибка: ${error.message}`, 'error');
            state.editingWord = null; // Exit editing mode on error
            render();
        }
    }


    function setupEventListeners() {
        dom.searchInput.addEventListener('input', (e) => {
            state.searchTerm = e.target.value;
            render();
        });

        dom.sortWordBtn.addEventListener('click', () => {
            state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
            render();
        });

        dom.addWordBtn.addEventListener('click', handleAddWord);
        dom.addWordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleAddWord();
        });

        dom.dictionaryTableBody.addEventListener('click', (e) => {
            const target = e.target;
            const row = target.closest('tr');
            if (!row) return;

            const originalWord = row.dataset.word;

            if (target.closest('.delete-word-btn')) {
                handleDeleteWord(originalWord);
            } else if (target.closest('.edit-word-btn')) {
                state.editingWord = originalWord;
                render();
            } else if (target.closest('.cancel-edit-btn')) {
                state.editingWord = null;
                render();
            } else if (target.closest('.save-edit-btn')) {
                const input = row.querySelector('.edit-word-input');
                handleUpdateWord(originalWord, input.value.trim());
            }
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