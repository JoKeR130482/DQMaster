document.addEventListener('DOMContentLoaded', () => {
    const templatesListContainer = document.getElementById('templates-list-container');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');
    const noTemplatesMessage = document.getElementById('no-templates-message');

    let allRules = []; // Cache for rule details

    // --- API Calls ---
    const fetchAllRules = async () => {
        try {
            const response = await fetch('/api/rules');
            if (!response.ok) throw new Error('Failed to fetch rules');
            allRules = await response.json();
        } catch (error) {
            showError(`Не удалось загрузить детали правил: ${error.message}`);
        }
    };

    const fetchTemplates = async () => {
        loadingSpinner.style.display = 'block';
        errorContainer.style.display = 'none';
        noTemplatesMessage.style.display = 'none';
        try {
            const response = await fetch('/api/templates');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const templates = await response.json();
            renderTemplates(templates);
        } catch (error) {
            showError(`Не удалось загрузить шаблоны: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

    // --- Rendering ---
    const renderTemplates = (templates) => {
        templatesListContainer.innerHTML = '';
        if (templates.length === 0) {
            noTemplatesMessage.style.display = 'block';
            return;
        }
        templates.forEach(template => {
            const templateCard = document.createElement('div');
            templateCard.className = 'template-card';
            templateCard.innerHTML = `
                <div class="template-header">
                    <h3 class="template-name">${template.name}</h3>
                    <button class="delete-template-btn" data-id="${template.id}" title="Удалить шаблон">&times;</button>
                </div>
                <div class="template-body">
                    <p><strong>Колонки:</strong> ${template.columns.join(', ')}</p>
                    <div class="template-rules">
                        <strong>Правила:</strong>
                        <ul>
                            ${Object.entries(template.rules).map(([col, ruleIds]) => {
                                if (ruleIds.length === 0) return '';
                                const ruleNames = ruleIds.map(id => allRules.find(r => r.id === id)?.name || id).join(', ');
                                return `<li><strong>${col}:</strong> ${ruleNames}</li>`;
                            }).join('')}
                        </ul>
                    </div>
                </div>
            `;
            templatesListContainer.appendChild(templateCard);
        });
    };

    const showError = (message) => {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
    };

    // --- Event Handlers ---
    templatesListContainer.addEventListener('click', async (event) => {
        if (event.target.classList.contains('delete-template-btn')) {
            const templateId = event.target.dataset.id;
            if (!templateId) return;

            if (confirm('Вы уверены, что хотите удалить этот шаблон?')) {
                try {
                    const response = await fetch(`/api/templates/${templateId}`, { method: 'DELETE' });
                    if (!response.ok) {
                         // Try to get error detail from server
                        const errorData = await response.json().catch(() => null);
                        throw new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
                    }
                    // Refresh the list on successful deletion
                    fetchTemplates();
                } catch (error) {
                    showError(`Не удалось удалить шаблон: ${error.message}`);
                }
            }
        }
    });

    // --- Initial Load ---
    const init = async () => {
        await fetchAllRules(); // Fetch rule details first
        await fetchTemplates(); // Then fetch and render templates
    };

    init();
});