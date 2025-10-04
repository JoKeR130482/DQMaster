document.addEventListener('DOMContentLoaded', () => {
    // --- 1. DOM Elements ---
    const fileInput = document.getElementById('fileInput');
    const fileLabel = document.querySelector('.file-label');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');
    const sheetSelectModal = document.getElementById('sheet-select-modal');
    const sheetListDiv = document.getElementById('sheet-list');
    const templateSuggestionContainer = document.getElementById('template-suggestion-container');
    const templateSuggestionsList = document.getElementById('template-suggestions-list');
    const skipTemplatesBtn = document.getElementById('skip-templates-btn');
    const columnsConfigContainer = document.getElementById('columns-config-container');
    const columnsListDiv = document.getElementById('columns-list');
    const saveTemplateBtn = document.getElementById('save-template-btn');
    const validateButton = document.getElementById('validateButton');
    const resultsContainer = document.getElementById('validation-results-container');
    const summaryResultsDiv = document.getElementById('summary-results');
    const detailedResultsDiv = document.getElementById('detailed-results');
    const saveTemplateModal = document.getElementById('save-template-modal');
    const templateNameInput = document.getElementById('template-name-input');
    const confirmSaveBtn = document.getElementById('confirm-save-btn');
    const cancelSaveBtn = document.getElementById('cancel-save-btn');
    const ruleConfigModal = document.getElementById('rule-config-modal');
    const ruleConfigTitle = document.getElementById('rule-config-title');
    const ruleConfigForm = document.getElementById('rule-config-form');
    const confirmRuleConfigBtn = document.getElementById('confirm-rule-config-btn');
    const cancelRuleConfigBtn = document.getElementById('cancel-rule-config-btn');

    // --- 2. Application State ---
    let currentFileId = null;
    let currentSheetName = null;
    let currentColumns = [];
    let availableRules = [];
    let appliedRules = {}; // Structure: { "columnName": { is_required: boolean, rules: [ruleConfig, ...] } }
    let pendingRuleConfig = {};

    // --- 3. Helper Functions ---
    const resetUI = (isNewFile = true) => {
        sheetSelectModal.style.display = 'none';
        templateSuggestionContainer.style.display = 'none';
        columnsConfigContainer.style.display = 'none';
        resultsContainer.style.display = 'none';
        errorContainer.style.display = 'none';
        summaryResultsDiv.innerHTML = '';
        detailedResultsDiv.innerHTML = '';
        if (isNewFile) {
            fileLabel.textContent = 'Выберите файл...';
            currentFileId = null;
            currentSheetName = null;
            currentColumns = [];
        }
        appliedRules = {};
    };

    const showNotification = (message, type = 'success') => { /* ... (no changes) ... */ };
    const showError = (message) => showNotification(message, 'error');

    const formatRuleDisplayName = (ruleDef, ruleConfig) => { /* ... (no changes) ... */ };

    // --- 4. API Calls & Logic Chain ---
    const fetchAvailableRules = async () => { /* ... (no changes) ... */ };

    const handleSheetSelection = async (sheetName) => {
        currentSheetName = sheetName;
        sheetSelectModal.style.display = 'none';
        loadingSpinner.style.display = 'block';
        try {
            const response = await fetch('/api/select-sheet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fileId: currentFileId, sheetName: currentSheetName })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to select sheet');
            currentColumns = data.columns;
            // **MODIFIED**: Initialize with new structure
            currentColumns.forEach(col => { appliedRules[col] = { is_required: false, rules: [] }; });
            await findMatchingTemplates();
        } catch (error) {
            showError(`Ошибка выбора листа: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

    const findMatchingTemplates = async () => {
        loadingSpinner.style.display = 'block';
        try {
            const response = await fetch('/api/templates/find-matches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ columns: currentColumns })
            });
            if (!response.ok) throw new Error('Failed to find matching templates');
            const templates = await response.json();
            showTemplateSuggestions(templates);
        } catch (error) {
            showError(`Ошибка поиска шаблонов: ${error.message}`);
            renderColumnsConfig(); // Fallback
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

    const showTemplateSuggestions = (templates) => {
        if (templates.length === 0) {
            renderColumnsConfig();
            return;
        }

        templateSuggestionContainer.style.display = 'block';
        templateSuggestionsList.innerHTML = ''; // Clear old suggestions

        templates.forEach(template => {
            const card = document.createElement('div');
            card.className = 'template-suggestion';
            card.dataset.id = template.id;
            card.innerHTML = `<h4>${template.name}</h4><p>Нажмите, чтобы применить этот шаблон.</p>`;

            card.addEventListener('click', () => {
                appliedRules = template.rules;
                templateSuggestionContainer.style.display = 'none';
                renderColumnsConfig();
                showNotification(`Шаблон "${template.name}" применен.`);
            });

            templateSuggestionsList.appendChild(card);
        });
    };

    // --- 5. UI Rendering ---
    const showSheetSelectionModal = (sheets) => {
        sheetListDiv.innerHTML = '';
        sheets.forEach(name => {
            const sheetButton = document.createElement('button');
            sheetButton.className = 'sheet-button';
            sheetButton.textContent = name;
            sheetButton.addEventListener('click', () => handleSheetSelection(name));
            sheetListDiv.appendChild(sheetButton);
        });
        sheetSelectModal.style.display = 'flex';
    };

    const renderColumnsConfig = () => {
        columnsListDiv.innerHTML = '';
        currentColumns.forEach(column => {
            if (!appliedRules[column]) appliedRules[column] = { is_required: false, rules: [] };

            const columnConfig = appliedRules[column];
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
                <div class="applied-rules-container" id="rules-for-${column}"></div>
            `;
            columnsListDiv.appendChild(columnDiv);
            renderAppliedRulesForColumn(column);
        });
        columnsConfigContainer.style.display = 'block';
    };

    const renderAppliedRulesForColumn = (columnName) => {
        const container = document.getElementById(`rules-for-${columnName}`);
        if (!container) return;
        container.innerHTML = '';
        appliedRules[columnName].rules.forEach((ruleConfig, index) => {
            const ruleDef = availableRules.find(r => r.id === ruleConfig.id);
            if (!ruleDef) return;
            const ruleDisplayName = formatRuleDisplayName(ruleDef, ruleConfig);
            const ruleTag = document.createElement('div');
            ruleTag.className = 'rule-tag';
            ruleTag.innerHTML = `<span title="${ruleDef.description}">${ruleDisplayName}</span><button class="remove-rule-btn" data-column="${columnName}" data-index="${index}">&times;</button>`;
            container.appendChild(ruleTag);
        });
    };

    const openRuleConfigModal = (rule, columnName, existingConfig = null, index = -1) => { /* ... (no changes) ... */ };
    const renderValidationResults = (results) => {
        const goldenRecordStatsDiv = document.getElementById('golden-record-stats');
        const summaryResultsDiv = document.getElementById('summary-results');
        const detailedResultsDiv = document.getElementById('detailed-results');

        // Clear all previous results
        goldenRecordStatsDiv.innerHTML = '';
        summaryResultsDiv.innerHTML = '';
        detailedResultsDiv.innerHTML = '';
        resultsContainer.style.display = 'block';

        const totalRows = results.total_rows || 0;
        const errorRowsCount = results.error_rows_count || 0;
        const errorPercentage = totalRows > 0 ? ((errorRowsCount / totalRows) * 100).toFixed(2) : 0;

        // Render Golden Record Stats
        goldenRecordStatsDiv.innerHTML = `
            <div class="stats-summary">
                <span>Всего строк: <strong>${totalRows}</strong></span>
                <span>Строк с ошибками: <strong>${errorRowsCount}</strong></span>
                <span>Процент ошибочных строк: <strong>${errorPercentage}%</strong></span>
            </div>
        `;

        if (!results.errors || results.errors.length === 0) {
            summaryResultsDiv.innerHTML = '<div class="success-message">Проверка успешно завершена. Ошибок не найдено!</div>';
            return;
        }

        // Aggregate per-rule errors for the summary table
        const errorsByRule = results.errors.reduce((acc, error) => {
            if (!acc[error.rule_name]) acc[error.rule_name] = [];
            acc[error.rule_name].push(error);
            return acc;
        }, {});

        // Render per-rule summary table
        const summaryTable = document.createElement('table');
        summaryTable.className = 'results-table summary-table';
        summaryTable.innerHTML = `
            <thead><tr><th>Детализация по правилам</th><th>Количество ошибок</th></tr></thead>
            <tbody>
                ${Object.entries(errorsByRule).map(([ruleName, errors]) => `
                    <tr class="summary-row" data-rule-name="${ruleName}">
                        <td>${ruleName}</td>
                        <td>${errors.length}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        summaryResultsDiv.appendChild(summaryTable);

        // Add click listener for details
        summaryTable.querySelector('tbody').addEventListener('click', (event) => {
            const row = event.target.closest('.summary-row');
            if (!row) return;
            document.querySelectorAll('.summary-row').forEach(r => r.classList.remove('active'));
            row.classList.add('active');
            renderDetailedTable(errorsByRule[row.dataset.ruleName]);
        });
    };

    const renderDetailedTable = (errors) => {
        const detailedResultsDiv = document.getElementById('detailed-results');
        detailedResultsDiv.innerHTML = '';
        if (!errors || errors.length === 0) return;
        const detailTable = document.createElement('table');
        detailTable.className = 'results-table detail-table';
        detailTable.innerHTML = `
            <caption>Детали по ошибкам для: "${errors[0].rule_name}"</caption>
            <thead><tr><th>Строка</th><th>Колонка</th><th>Значение</th></tr></thead>
            <tbody>
                ${errors.map(e => `<tr><td>${e.row}</td><td>${e.column}</td><td>${e.value}</td></tr>`).join('')}
            </tbody>
        `;
        detailedResultsDiv.appendChild(detailTable);
    };
    const showTemplateSuggestions = (templates) => { /* ... (no changes) ... */ };

    // --- 6. Event Handlers ---
    fileInput.addEventListener('change', async (event) => { /* ... (no changes) ... */ });

    validateButton.addEventListener('click', async () => {
        if (!currentFileId || !currentSheetName) return showError("Файл или лист не выбраны для проверки.");
        loadingSpinner.style.display = 'block';
        resultsContainer.style.display = 'none';
        try {
            const payload = { fileId: currentFileId, sheetName: currentSheetName, rules: appliedRules }; // **MODIFIED**: appliedRules now has the correct structure
            const response = await fetch('/api/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const results = await response.json();
            if (!response.ok) throw new Error(results.detail || 'Validation failed');
            renderValidationResults(results);
        } catch (error) {
            showError(`Ошибка проверки: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    });

    skipTemplatesBtn.addEventListener('click', () => { /* ... (no changes) ... */ });

    columnsListDiv.addEventListener('change', (event) => {
        // Handle "is_required" checkbox
        if (event.target.classList.contains('required-checkbox')) {
            const columnName = event.target.dataset.column;
            if (appliedRules[columnName]) {
                appliedRules[columnName].is_required = event.target.checked;
            }
            return;
        }

        // Handle rule selection
        if (event.target.classList.contains('rule-select')) {
            const selectedRuleId = event.target.value; if (!selectedRuleId) return;
            const rule = availableRules.find(r => r.id === selectedRuleId);
            const columnName = event.target.closest('.column-config').querySelector('.column-name').textContent;
            if (rule.is_configurable) { openRuleConfigModal(rule, columnName); }
            else {
                const newRule = { id: selectedRuleId, params: null };
                // **MODIFIED**: Check within the .rules array
                if (appliedRules[columnName].rules.some(r => JSON.stringify(r) === JSON.stringify(newRule))) {
                    showNotification('Это правило уже добавлено.', 'error');
                } else {
                    appliedRules[columnName].rules.push(newRule);
                    renderAppliedRulesForColumn(columnName);
                }
            }
            event.target.value = "";
        }
    });

    confirmRuleConfigBtn.addEventListener('click', () => {
        const { rule, columnName, index } = pendingRuleConfig; const params = {};
        if (rule.id === 'substring_check') { /* ... (no changes) ... */ }
        const newRule = { id: rule.id, params: params };

        if (index > -1) { // Editing existing rule
            appliedRules[columnName].rules[index] = newRule;
        } else { // Adding new rule
            // **MODIFIED**: Check within the .rules array
            if (appliedRules[columnName].rules.some(r => JSON.stringify(r) === JSON.stringify(newRule))) {
                showNotification('Правило с такими же параметрами уже добавлено.', 'error');
                return;
            }
            appliedRules[columnName].rules.push(newRule);
        }
        renderAppliedRulesForColumn(columnName);
        ruleConfigModal.style.display = 'none';
        pendingRuleConfig = {};
    });

    cancelRuleConfigBtn.addEventListener('click', () => { /* ... (no changes) ... */ });

    columnsListDiv.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-rule-btn')) {
            const { column, index } = event.target.dataset;
            appliedRules[column].rules.splice(index, 1); // **MODIFIED**: Splice from the .rules array
            renderAppliedRulesForColumn(column);
        }
    });

    saveTemplateBtn.addEventListener('click', () => { /* ... (no changes) ... */ });
    cancelSaveBtn.addEventListener('click', () => { /* ... (no changes) ... */ });
    confirmSaveBtn.addEventListener('click', async () => { /* ... (no changes) ... */ });

    // --- 7. Initial Load ---
    fetchAvailableRules();
});