document.addEventListener('DOMContentLoaded', () => {
    const rulesListContainer = document.getElementById('rules-list-container');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');
    const searchInput = document.getElementById('searchInput');
    const sortByNameBtn = document.getElementById('sortByName');
    const sortByNameDescBtn = document.getElementById('sortByNameDesc');

    let allRules = []; // Cache for all rules fetched from the server

    // --- Data Fetching ---
    const fetchRules = async () => {
        loadingSpinner.style.display = 'block';
        errorContainer.style.display = 'none';
        try {
            const response = await fetch('/api/rules');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            allRules = await response.json();
            renderRules(allRules);
        } catch (error) {
            errorContainer.textContent = `Не удалось загрузить правила: ${error.message}`;
            errorContainer.style.display = 'block';
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

    // --- Rendering ---
    const renderRules = (rules) => {
        rulesListContainer.innerHTML = ''; // Clear previous content
        if (rules.length === 0) {
            rulesListContainer.innerHTML = '<p>Правила не найдены.</p>';
            return;
        }
        rules.forEach(rule => {
            const ruleElement = document.createElement('div');
            ruleElement.className = 'rule-card';
            ruleElement.innerHTML = `
                <h3 class="rule-name">${rule.name}</h3>
                <p class="rule-description">${rule.description}</p>
                <code class="rule-id">ID: ${rule.id}</code>
            `;
            rulesListContainer.appendChild(ruleElement);
        });
    };

    // --- Event Listeners for Sorting and Filtering ---
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredRules = allRules.filter(rule =>
            rule.name.toLowerCase().includes(searchTerm) ||
            rule.description.toLowerCase().includes(searchTerm)
        );
        renderRules(filteredRules);
    });

    sortByNameBtn.addEventListener('click', () => {
        const sortedRules = [...allRules].sort((a, b) => a.name.localeCompare(b.name));
        renderRules(sortedRules);
    });

    sortByNameDescBtn.addEventListener('click', () => {
        const sortedRules = [...allRules].sort((a, b) => b.name.localeCompare(a.name));
        renderRules(sortedRules);
    });

    // --- Initial Load ---
    fetchRules();
});