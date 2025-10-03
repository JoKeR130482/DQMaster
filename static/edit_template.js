document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const editContainer = document.getElementById('edit-container');
    const templateNameInput = document.getElementById('template-name-input');
    const columnsListDiv = document.getElementById('columns-list');
    const saveChangesBtn = document.getElementById('save-changes-btn');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');

    // Rule Config Modal Elements
    const ruleConfigModal = document.getElementById('rule-config-modal');
    const ruleConfigTitle = document.getElementById('rule-config-title');
    const ruleConfigForm = document.getElementById('rule-config-form');
    const confirmRuleConfigBtn = document.getElementById('confirm-rule-config-btn');
    const cancelRuleConfigBtn = document.getElementById('cancel-rule-config-btn');

    // --- State ---
    let templateId = null;
    let availableRules = [];
    let currentTemplate = null;
    let pendingRuleConfig = {};

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
        toast.classList.add(type === 'error' ? 'error' : 'success');

        setTimeout(() => { toast.classList.remove('show'); }, 3000);
    };

    const showError = (message) => showNotification(message, 'error');

    // --- API Calls ---
    const fetchData = async () => {
        try {
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

        rulesForColumn.forEach((ruleConfig, index) => {
            const ruleDef = availableRules.find(r => r.id === ruleConfig.id);
            if (!ruleDef) return;

            let ruleDisplayName = ruleDef.name;
            // A more robust formatter logic might be needed for different rules
            if (ruleDef.is_configurable && ruleConfig.params && ruleConfig.params.value) {
                 const modeText = ruleConfig.params.mode === 'contains' ? 'содержит' : 'не содержит';
                 ruleDisplayName = `${ruleDef.name} (${modeText}: '${ruleConfig.params.value}')`;
            }

            const ruleTag = document.createElement('div');
            ruleTag.className = 'rule-tag';
            ruleTag.innerHTML = `
                <span title="${ruleDef.description}">${ruleDisplayName}</span>
                <button class="remove-rule-btn" data-column="${columnName}" data-index="${index}">&times;</button>
            `;
            container.appendChild(ruleTag);
        });
    };

    const openRuleConfigModal = (rule, columnName) => {
        pendingRuleConfig = { rule, columnName };
        ruleConfigTitle.textContent = `Настроить правило: ${rule.name}`;

        if (rule.id === 'substring_check') {
            ruleConfigForm.innerHTML = `
                <label for="rule-mode">Режим:</label>
                <select id="rule-mode" class="rule-param-input">
                    <option value="contains">содержит</option>
                    <option value="not_contains">не содержит</option>
                </select>
                <label for="rule-value">Значение:</label>
                <input type="text" id="rule-value" class="rule-param-input" placeholder="Введите подстроку...">
                <div class="checkbox-container">
                    <input type="checkbox" id="rule-case-sensitive" class="rule-param-input">
                    <label for="rule-case-sensitive">Учитывать регистр</label>
                </div>
            `;
        } else {
            ruleConfigForm.innerHTML = '<p>Это правило не требует дополнительной настройки.</p>';
        }

        ruleConfigModal.style.display = 'flex';
    };

    // --- Event Handlers ---
    columnsListDiv.addEventListener('change', (event) => {
        if (event.target.classList.contains('rule-select')) {
            const selectedRuleId = event.target.value;
            if (!selectedRuleId) return;

            const rule = availableRules.find(r => r.id === selectedRuleId);
            const columnName = event.target.closest('.column-config').querySelector('.column-name').textContent;

            if (!currentTemplate.rules[columnName]) {
                currentTemplate.rules[columnName] = [];
            }

            if (rule.is_configurable) {
                openRuleConfigModal(rule, columnName);
            } else {
                currentTemplate.rules[columnName].push({ id: selectedRuleId, params: null });
                renderAppliedRulesForColumn(columnName);
            }
            event.target.value = "";
        }
    });

    confirmRuleConfigBtn.addEventListener('click', () => {
        const { rule, columnName } = pendingRuleConfig;
        const params = {};

        if (rule.id === 'substring_check') {
            params.mode = document.getElementById('rule-mode').value;
            params.value = document.getElementById('rule-value').value;
            params.case_sensitive = document.getElementById('rule-case-sensitive').checked;
            if (!params.value) return showError('Значение для проверки не может быть пустым.');
        }

        currentTemplate.rules[columnName].push({ id: rule.id, params: params });
        renderAppliedRulesForColumn(columnName);

        ruleConfigModal.style.display = 'none';
        pendingRuleConfig = {};
    });

    cancelRuleConfigBtn.addEventListener('click', () => {
        ruleConfigModal.style.display = 'none';
        pendingRuleConfig = {};
    });

    columnsListDiv.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-rule-btn')) {
            const { column, index } = event.target.dataset;
            currentTemplate.rules[column].splice(index, 1);
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
            setTimeout(() => { window.location.href = '/templates'; }, 1000);
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