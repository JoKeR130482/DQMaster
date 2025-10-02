document.addEventListener('DOMContentLoaded', () => {
    // --- Main DOM Elements ---
    const templatesListContainer = document.getElementById('templates-list-container');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');
    const noTemplatesMessage = document.getElementById('no-templates-message');

    // --- State ---
    let allRules = [];

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
                    <div class="template-actions">
                        <button class="edit-template-btn" data-id="${template.id}">Редактировать</button>
                        <button class="delete-template-btn" data-id="${template.id}">Удалить</button>
                    </div>
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
        const target = event.target;

        // Handle Delete
        if (target.classList.contains('delete-template-btn')) {
            const templateId = target.dataset.id;
            if (!templateId) return;
            if (confirm('Вы уверены, что хотите удалить этот шаблон?')) {
                try {
                    const response = await fetch(`/api/templates/${templateId}`, { method: 'DELETE' });
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    fetchTemplates();
                } catch (error) {
                    showError(`Не удалось удалить шаблон: ${error.message}`);
                }
            }
        }

        // Handle Edit - Redirect to edit page
        if (target.classList.contains('edit-template-btn')) {
            const templateId = target.dataset.id;
            if (templateId) {
                window.location.href = `/templates/edit/${templateId}`;
            }
        }
    });

    // --- Initial Load ---
    const init = async () => {
        await fetchAllRules();
        await fetchTemplates();
    };

    init();
});