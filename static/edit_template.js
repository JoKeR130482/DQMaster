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
    let currentTemplate = null;
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

    // --- UI Rendering (Robust version using createElement) ---
    const renderEditor = () => {
        templateNameInput.value = currentTemplate.name;
        columnsListDiv.innerHTML = '';

        currentTemplate.columns.forEach(column => {
            const columnDiv = document.createElement('div');
            columnDiv.className = 'column-config';

            const columnHeader = document.createElement('div');
            columnHeader.className = 'column-header';

            const columnNameSpan = document.createElement('span');
            columnNameSpan.className = 'column-name';
            columnNameSpan.textContent = column;

            const ruleControlsDiv = document.createElement('div');
            ruleControlsDiv.className = 'rule-controls';

            const select = document.createElement('select');
            select.className = 'rule-select';

            const defaultOption = document.createElement('option');
            defaultOption.value = "";
            defaultOption.textContent = "-- Добавить правило --";
            select.appendChild(defaultOption);

            availableRules.forEach(rule => {
                const option = document.createElement('option');
                option.value = rule.id;
                option.textContent = rule.name;
                select.appendChild(option);
            });

            ruleControlsDiv.appendChild(select);
            columnHeader.appendChild(columnNameSpan);
            columnHeader.appendChild(ruleControlsDiv);

            const appliedRulesContainer = document.createElement('div');
            appliedRulesContainer.className = 'applied-rules-container';
            appliedRulesContainer.id = `rules-for-edit-${column}`;

            columnDiv.appendChild(columnHeader);
            columnDiv.appendChild(appliedRulesContainer);

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

            const ruleDisplayName = formatRuleDisplayName(ruleDef, ruleConfig);

            const ruleTag = document.createElement('div');
            ruleTag.className = 'rule-tag';

            const span = document.createElement('span');
            span.title = ruleDef.description;
            span.textContent = ruleDisplayName;

            const button = document.createElement('button');
            button.className = 'remove-rule-btn';
            button.innerHTML = '&times;';
            button.dataset.column = columnName;
            button.dataset.index = index;

            ruleTag.appendChild(span);
            ruleTag.appendChild(button);
            container.appendChild(ruleTag);
        });
    };

    // ... (rest of the event handlers are the same and correct) ...
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
                const newRule = { id: selectedRuleId, params: null };
                const isDuplicate = currentTemplate.rules[columnName].some(existingRule => JSON.stringify(existingRule) === JSON.stringify(newRule));
                if (isDuplicate) {
                    showNotification('Это правило уже добавлено к данной колонке.', 'error');
                } else {
                    currentTemplate.rules[columnName].push(newRule);
                    renderAppliedRulesForColumn(columnName);
                }
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

        const newRule = { id: rule.id, params: params };
        const isDuplicate = currentTemplate.rules[columnName].some(existingRule => JSON.stringify(existingRule) === JSON.stringify(newRule));

        if (isDuplicate) {
            showNotification('Правило с такими же параметрами уже добавлено.', 'error');
        } else {
            currentTemplate.rules[columnName].push(newRule);
            renderAppliedRulesForColumn(columnName);
            ruleConfigModal.style.display = 'none';
        }
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