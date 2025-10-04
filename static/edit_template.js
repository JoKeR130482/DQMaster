document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const editContainer = document.getElementById('edit-container');
    const templateNameInput = document.getElementById('template-name-input');
    const columnsListDiv = document.getElementById('columns-list');
    const saveChangesBtn = document.getElementById('save-changes-btn');
    const loadingSpinner = document.getElementById('loading');
    const ruleConfigModal = document.getElementById('rule-config-modal');
    const ruleConfigTitle = document.getElementById('rule-config-title');
    const ruleConfigForm = document.getElementById('rule-config-form');
    const confirmRuleConfigBtn = document.getElementById('confirm-rule-config-btn');
    const cancelRuleConfigBtn = document.getElementById('cancel-rule-config-btn');

    // --- State ---
    let templateId = null;
    let availableRules = [];
    let currentTemplate = null; // Will hold the full template object, including the new structure
    let pendingRuleConfig = {};

    // --- Helper Functions ---
    const getTemplateIdFromUrl = () => window.location.pathname.split('/').pop();

    const showNotification = (message, type = 'success') => {
        const toast = document.getElementById('notification-toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = 'toast show';
        toast.classList.add(type === 'error' ? 'error' : 'success');
        setTimeout(() => { toast.classList.remove('show'); }, 3000);
    };

    const showError = (message) => showNotification(message, 'error');

    const formatRuleDisplayName = (ruleDef, ruleConfig) => {
        if (ruleDef.id === 'substring_check' && ruleConfig.params) {
            const modeText = ruleConfig.params.mode === 'contains' ? 'содержит (стоп-слово)' : 'не содержит (обязательно)';
            const caseText = ruleConfig.params.case_sensitive ? 'с уч. регистра' : 'без уч. регистра';
            return `${ruleDef.name} (${modeText}: '${ruleConfig.params.value}', ${caseText})`;
        }
        return ruleDef.name;
    };

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
            if (!currentTemplate) throw new Error('Шаблон не найден');
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
            const columnConfig = currentTemplate.rules[column] || { is_required: false, rules: [] };
            const isChecked = columnConfig.is_required ? 'checked' : '';

            const columnDiv = document.createElement('div');
            columnDiv.className = 'column-config';
            columnDiv.innerHTML = `
                <div class="column-header">
                    <span class="column-name">${column}</span>
                    <div class="column-actions">
                         <div class="checkbox-container required-field-container">
                            <input type="checkbox" id="required-check-${column}" class="required-checkbox" data-column="${column}" ${isChecked}>
                            <label for="required-check-${column}">Обязательное</label>
                        </div>
                        <div class="rule-controls">
                            <select class="rule-select">
                                <option value="">-- Добавить правило --</option>
                                ${availableRules.map(rule => `<option value="${rule.id}">${rule.name}</option>`).join('')}
                            </select>
                        </div>
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
        const rulesForColumn = currentTemplate.rules[columnName]?.rules || [];
        container.innerHTML = '';
        rulesForColumn.forEach((ruleConfig, index) => {
            const ruleDef = availableRules.find(r => r.id === ruleConfig.id);
            if (!ruleDef) return;
            const ruleDisplayName = formatRuleDisplayName(ruleDef, ruleConfig);
            const ruleTag = document.createElement('div');
            ruleTag.className = 'rule-tag';
            ruleTag.innerHTML = `
                <span class="clickable-rule" data-column="${columnName}" data-index="${index}" title="${ruleDef.description}">${ruleDisplayName}</span>
                <button class="remove-rule-btn" data-column="${columnName}" data-index="${index}">&times;</button>
            `;
            container.appendChild(ruleTag);
        });
    };

    const openRuleConfigModal = (rule, columnName, existingConfig = null, index = -1) => {
        pendingRuleConfig = { rule, columnName, index };
        ruleConfigTitle.textContent = `Настроить правило: ${rule.name}`;
        if (rule.id === 'substring_check') {
            ruleConfigForm.innerHTML = `
                <label for="rule-mode">Режим:</label>
                <select id="rule-mode" class="rule-param-input"><option value="contains">содержит (стоп-слово)</option><option value="not_contains">не содержит (обязательно)</option></select>
                <label for="rule-value">Значение:</label>
                <input type="text" id="rule-value" class="rule-param-input" placeholder="Введите подстроку...">
                <div class="checkbox-container"><input type="checkbox" id="rule-case-sensitive" class="rule-param-input"><label for="rule-case-sensitive">Учитывать регистр</label></div>
            `;
            if (existingConfig && existingConfig.params) {
                document.getElementById('rule-mode').value = existingConfig.params.mode || 'contains';
                document.getElementById('rule-value').value = existingConfig.params.value || '';
                document.getElementById('rule-case-sensitive').checked = existingConfig.params.case_sensitive || false;
            }
        } else {
            ruleConfigForm.innerHTML = '<p>Это правило не требует дополнительной настройки.</p>';
        }
        ruleConfigModal.style.display = 'flex';
    };

    // --- Event Handlers ---
    columnsListDiv.addEventListener('click', (event) => {
        const target = event.target;
        if (target.classList.contains('remove-rule-btn')) {
            const { column, index } = target.dataset;
            currentTemplate.rules[column].rules.splice(index, 1);
            renderAppliedRulesForColumn(column);
        }
        if (target.classList.contains('clickable-rule')) {
            const { column, index } = target.dataset;
            const ruleConfig = currentTemplate.rules[column].rules[index];
            const ruleDef = availableRules.find(r => r.id === ruleConfig.id);
            if(ruleDef && ruleDef.is_configurable) {
                openRuleConfigModal(ruleDef, column, ruleConfig, parseInt(index));
            }
        }
    });

    columnsListDiv.addEventListener('change', (event) => {
        const target = event.target;
        if (target.classList.contains('required-checkbox')) {
            const columnName = target.dataset.column;
            if (currentTemplate.rules[columnName]) {
                currentTemplate.rules[columnName].is_required = target.checked;
            }
        }
        if (target.classList.contains('rule-select')) {
            const selectedRuleId = target.value;
            if (!selectedRuleId) return;
            const rule = availableRules.find(r => r.id === selectedRuleId);
            const columnName = target.closest('.column-config').querySelector('.column-name').textContent;
            if (!currentTemplate.rules[columnName]) {
                currentTemplate.rules[columnName] = { is_required: false, rules: [] };
            }
            if (rule.is_configurable) {
                openRuleConfigModal(rule, columnName);
            } else {
                const newRule = { id: selectedRuleId, params: null };
                if (currentTemplate.rules[columnName].rules.some(r => JSON.stringify(r) === JSON.stringify(newRule))) {
                    showNotification('Это правило уже добавлено к данной колонке.', 'error');
                } else {
                    currentTemplate.rules[columnName].rules.push(newRule);
                    renderAppliedRulesForColumn(columnName);
                }
            }
            target.value = "";
        }
    });

    confirmRuleConfigBtn.addEventListener('click', () => {
        const { rule, columnName, index } = pendingRuleConfig;
        const params = {};
        if (rule.id === 'substring_check') {
            params.mode = document.getElementById('rule-mode').value;
            params.value = document.getElementById('rule-value').value;
            params.case_sensitive = document.getElementById('rule-case-sensitive').checked;
            if (!params.value) return showError('Значение для проверки не может быть пустым.');
        }
        const newRule = { id: rule.id, params: params };
        if (index > -1) {
            currentTemplate.rules[columnName].rules[index] = newRule;
        } else {
            if (currentTemplate.rules[columnName].rules.some(r => JSON.stringify(r) === JSON.stringify(newRule))) {
                showNotification('Правило с такими же параметрами уже добавлено.', 'error');
                return;
            }
            currentTemplate.rules[columnName].rules.push(newRule);
        }
        renderAppliedRulesForColumn(columnName);
        ruleConfigModal.style.display = 'none';
        pendingRuleConfig = {};
    });

    cancelRuleConfigBtn.addEventListener('click', () => {
        ruleConfigModal.style.display = 'none';
        pendingRuleConfig = {};
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