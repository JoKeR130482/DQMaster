document.addEventListener('DOMContentLoaded', () => {
    // --- Main DOM Elements ---
    const templatesListContainer = document.getElementById('templates-list-container');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');
    const noTemplatesMessage = document.getElementById('no-templates-message');

    // --- Edit Modal Elements ---
    const editTemplateModal = document.getElementById('edit-template-modal');
    const editTemplateNameInput = document.getElementById('edit-template-name-input');
    const confirmEditBtn = document.getElementById('confirm-edit-btn');
    const cancelEditBtn = document.getElementById('cancel-edit-btn');

    // --- State ---
    let allRules = [];
    let currentEditingTemplateId = null;

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
                        <button class="edit-template-btn" data-id="${template.id}" data-name="${template.name}" title="Редактировать имя">✏️</button>
                        <button class="delete-template-btn" data-id="${template.id}" title="Удалить шаблон">&times;</button>
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

        // Handle Edit - Show Modal
        if (target.classList.contains('edit-template-btn')) {
            currentEditingTemplateId = target.dataset.id;
            const currentName = target.dataset.name;
            editTemplateNameInput.value = currentName;
            editTemplateModal.style.display = 'flex';
            editTemplateNameInput.focus();
        }
    });

    // --- Edit Modal Handlers ---
    cancelEditBtn.addEventListener('click', () => {
        editTemplateModal.style.display = 'none';
        currentEditingTemplateId = null;
    });

    confirmEditBtn.addEventListener('click', async () => {
        if (!currentEditingTemplateId) return;

        const newName = editTemplateNameInput.value.trim();
        if (!newName) return showError('Имя шаблона не может быть пустым.');

        confirmEditBtn.disabled = true;
        confirmEditBtn.textContent = 'Сохранение...';

        try {
            const response = await fetch(`/api/templates/${currentEditingTemplateId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to update template');

            editTemplateModal.style.display = 'none';
            fetchTemplates(); // Refresh list to show the new name
        } catch (error) {
            showError(`Ошибка обновления: ${error.message}`);
        } finally {
            confirmEditBtn.disabled = false;
            confirmEditBtn.textContent = 'Сохранить';
            currentEditingTemplateId = null;
        }
    });

    // --- Initial Load ---
    const init = async () => {
        await fetchAllRules();
        await fetchTemplates();
    };

    init();
});