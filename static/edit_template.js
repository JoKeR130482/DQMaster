document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const editContainer = document.getElementById('edit-container');
    const templateNameInput = document.getElementById('template-name-input');
    const columnsListDiv = document.getElementById('columns-list');
    const saveChangesBtn = document.getElementById('save-changes-btn');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');

    // --- State ---
    let templateId = null;
    let availableRules = [];
    let currentTemplate = null;

    // --- Helper Functions ---
    const getTemplateIdFromUrl = () => {
        const pathParts = window.location.pathname.split('/');
        return pathParts[pathParts.length - 1];
    };

    const showNotification = (message, type = 'success') => {
        const toast = document.getElementById('notification-toast');
        if (!toast) return;

        toast.textContent = message;
        toast.className = 'toast show';
        if (type === 'error') {
            toast.classList.add('error');
        } else {
            toast.classList.add('success');
        }

        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    };

    const showError = (message) => {
        showNotification(message, 'error');
    };

    // --- API Calls ---
    const fetchData = async () => {
        try {
            // Fetch rules and template data in parallel
            const [rulesResponse, templatesResponse] = await Promise.all([
                fetch('/api/rules'),
                fetch('/api/templates')
            ]);

            if (!rulesResponse.ok) throw new Error('Failed to fetch rules');
            availableRules = await rulesResponse.json();

            if (!templatesResponse.ok) throw new Error('Failed to fetch templates');
            const allTemplates = await templatesResponse.json();

            currentTemplate = allTemplates.find(t => t.id === templateId);

            if (!currentTemplate) throw new Error('Template not found');

            renderEditor();
        } catch (error) {
            showError(error.message);
        } finally {
            loadingSpinner.style.display = 'none';
            editContainer.style.display = 'block';
        }
    };

    // --- UI Rendering ---
    const renderEditor = () => {
        templateNameInput.value = currentTemplate.name;
        columnsListDiv.innerHTML = '';

        currentTemplate.columns.forEach(column => {
            const columnDiv = document.createElement('div');
            columnDiv.className = 'column-config';
            columnDiv.innerHTML = `
                <div class="column-header">
                    <span class="column-name">${column}</span>
                    <div class="rule-controls">
                        <select class="rule-select">
                            <option value="">-- Добавить правило --</option>
                            ${availableRules.map(rule => `<option value="${rule.id}">${rule.name}</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="applied-rules-container" id="rules-for-edit-${column}"></div>
            `;
            columnsListDiv.appendChild(columnDiv);
            renderAppliedRulesForColumn(column);
        });
    };

    const renderAppliedRulesForColumn = (columnName) => {
        const container = document.getElementById(`rules-for-edit-${columnName}`);
        if (!container) return;

        const rulesForColumn = currentTemplate.rules[columnName] || [];
        container.innerHTML = '';

        rulesForColumn.forEach(ruleId => {
            const rule = availableRules.find(r => r.id === ruleId);
            if (!rule) return;

            const ruleTag = document.createElement('div');
            ruleTag.className = 'rule-tag';
            ruleTag.innerHTML = `
                <span title="${rule.description}">${rule.name}</span>
                <button class="remove-rule-btn" data-column="${columnName}" data-rule="${ruleId}">&times;</button>
            `;
            container.appendChild(ruleTag);
        });
    };

    // --- Event Handlers ---
    columnsListDiv.addEventListener('change', (event) => {
        if (event.target.classList.contains('rule-select')) {
            const selectedRuleId = event.target.value;
            if (!selectedRuleId) return;

            const columnName = event.target.closest('.column-config').querySelector('.column-name').textContent;
            if (!currentTemplate.rules[columnName]) {
                currentTemplate.rules[columnName] = [];
            }
            if (!currentTemplate.rules[columnName].includes(selectedRuleId)) {
                currentTemplate.rules[columnName].push(selectedRuleId);
                renderAppliedRulesForColumn(columnName);
            }
            event.target.value = ""; // Reset dropdown
        }
    });

    columnsListDiv.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-rule-btn')) {
            const { column, rule } = event.target.dataset;
            currentTemplate.rules[column] = currentTemplate.rules[column].filter(r => r !== rule);
            renderAppliedRulesForColumn(column);
        }
    });

    saveChangesBtn.addEventListener('click', async () => {
        const newName = templateNameInput.value.trim();
        if (!newName) return showError('Имя шаблона не может быть пустым.');

        currentTemplate.name = newName;

        saveChangesBtn.disabled = true;
        saveChangesBtn.textContent = 'Сохранение...';

        try {
            const response = await fetch(`/api/templates/${templateId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentTemplate)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to update template');

            showNotification('Шаблон успешно обновлен!');
            // Redirect after a short delay to allow user to see the message
            setTimeout(() => {
                window.location.href = '/templates';
            }, 1000);
        } catch (error) {
            showError(`Ошибка сохранения: ${error.message}`);
        } finally {
            saveChangesBtn.disabled = false;
            saveChangesBtn.textContent = 'Сохранить изменения';
        }
    });

    // --- Initial Load ---
    templateId = getTemplateIdFromUrl();
    if (templateId) {
        fetchData();
    } else {
        showError("ID шаблона не найден в URL.");
        loadingSpinner.style.display = 'none';
    }
});