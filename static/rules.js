document.addEventListener('DOMContentLoaded', () => {
    const rulesListContainer = document.getElementById('rules-list-container');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');
    const searchInput = document.getElementById('searchInput');
    const sortByNameBtn = document.getElementById('sortByName');
    const sortByNameDescBtn = document.getElementById('sortByNameDesc');
    const showGroupsOnlyBtn = document.getElementById('show-groups-only-btn');

    let allRules = [];
    let allGroups = [];
    let showGroupsOnly = false;

    // --- Data Fetching ---
    const fetchData = async () => {
        loadingSpinner.style.display = 'block';
        errorContainer.style.display = 'none';
        try {
            const [rulesRes, groupsRes] = await Promise.all([
                fetch('/api/rules'),
                fetch('/api/rule-groups')
            ]);
            if (!rulesRes.ok || !groupsRes.ok) {
                throw new Error('Network response was not ok');
            }
            allRules = await rulesRes.json();
            allGroups = await groupsRes.json();
            render();
        } catch (error) {
            errorContainer.textContent = `Не удалось загрузить данные: ${error.message}`;
            errorContainer.style.display = 'block';
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

    // --- Rendering ---
    const render = () => {
        rulesListContainer.innerHTML = '';
        const searchTerm = searchInput.value.toLowerCase();

        let itemsToShow = showGroupsOnly
            ? allGroups.map(g => ({ ...g, is_group: true }))
            : [...allRules, ...allGroups.map(g => ({ ...g, is_group: true }))];

        const filteredItems = itemsToShow.filter(item =>
            item.name.toLowerCase().includes(searchTerm) ||
            (item.description && item.description.toLowerCase().includes(searchTerm))
        );

        if (filteredItems.length === 0) {
            rulesListContainer.innerHTML = '<p>Ничего не найдено.</p>';
            return;
        }

        filteredItems.forEach(item => {
            const card = document.createElement('div');
            card.className = 'rule-card';
            if (item.is_group) {
                card.innerHTML = `
                    <h3 class="rule-name">${item.name} <span class="badge" style="background-color: #e0e7ff; color: #4338ca; padding: 2px 6px; border-radius: 4px; font-size: 0.8em;">Группа</span></h3>
                    <p class="rule-description">Логика: <strong>${item.logic}</strong>. Правил: ${item.rules.length}</p>
                    <code class="rule-id">ID: ${item.id}</code>
                `;
            } else {
                card.innerHTML = `
                    <h3 class="rule-name">${item.name}</h3>
                    <p class="rule-description">${item.description}</p>
                    <code class="rule-id">ID: ${item.id}</code>
                `;
            }
            rulesListContainer.appendChild(card);
        });
    };

    // --- Event Listeners ---
    searchInput.addEventListener('input', render);

    showGroupsOnlyBtn.addEventListener('click', () => {
        showGroupsOnly = !showGroupsOnly;
        showGroupsOnlyBtn.textContent = showGroupsOnly ? 'Показать все' : 'Показать только группы';
        render();
    });

    sortByNameBtn.addEventListener('click', () => {
        const sorter = (a, b) => a.name.localeCompare(b.name);
        allRules.sort(sorter);
        allGroups.sort(sorter);
        render();
    });

    sortByNameDescBtn.addEventListener('click', () => {
        const sorter = (a, b) => b.name.localeCompare(a.name);
        allRules.sort(sorter);
        allGroups.sort(sorter);
        render();
    });

    // --- Initial Load ---
    fetchData();
});