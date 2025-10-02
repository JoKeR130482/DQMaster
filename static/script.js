document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const fileInput = document.getElementById('fileInput');
    const fileLabel = document.querySelector('.file-label');
    const loadingSpinner = document.getElementById('loading');
    const errorContainer = document.getElementById('error-container');

    // Template Suggestions
    const templateSuggestionContainer = document.getElementById('template-suggestion-container');
    const templateSuggestionsList = document.getElementById('template-suggestions-list');
    const skipTemplatesBtn = document.getElementById('skip-templates-btn');

    // Columns Configuration
    const columnsConfigContainer = document.getElementById('columns-config-container');
    const columnsListDiv = document.getElementById('columns-list');
    const saveTemplateBtn = document.getElementById('save-template-btn');
    const validateButton = document.getElementById('validateButton');

    // Validation Results
    const resultsContainer = document.getElementById('validation-results-container');
    const resultsOutputDiv = document.getElementById('results-output');

    // Modal Elements
    const saveTemplateModal = document.getElementById('save-template-modal');
    const templateNameInput = document.getElementById('template-name-input');
    const confirmSaveBtn = document.getElementById('confirm-save-btn');
    const cancelSaveBtn = document.getElementById('cancel-save-btn');

    // --- Application State ---
    let currentFileId = null;
    let currentColumns = [];
    let availableRules = [];
    let appliedRules = {};

    // --- Helper Functions ---
    const resetUI = (isNewFile = true) => {
        templateSuggestionContainer.style.display = 'none';
        columnsConfigContainer.style.display = 'none';
        resultsContainer.style.display = 'none';
        errorContainer.style.display = 'none';

        // Also clear the content of the results containers
        document.getElementById('summary-results').innerHTML = '';
        document.getElementById('detailed-results').innerHTML = '';

        if (isNewFile) {
            fileLabel.textContent = 'Выберите файл...';
            currentFileId = null;
            currentColumns = [];
        }
        appliedRules = {};
    };

    const showError = (message) => {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
    };

    // --- API Calls ---
    const fetchAvailableRules = async () => {
        try {
            const response = await fetch('/api/rules');
            if (!response.ok) throw new Error('Failed to fetch rules');
            availableRules = await response.json();
        } catch (error) {
            showError(`Не удалось загрузить правила: ${error.message}`);
        }
    };

    // --- UI Rendering & Logic ---
    const renderColumnsConfig = () => {
        columnsListDiv.innerHTML = '';
        currentColumns.forEach(column => {
            if (!appliedRules[column]) {
                appliedRules[column] = [];
            }

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
        appliedRules[columnName].forEach(ruleId => {
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

    const renderValidationResults = (results) => {
        const summaryResultsDiv = document.getElementById('summary-results');
        const detailedResultsDiv = document.getElementById('detailed-results');

        summaryResultsDiv.innerHTML = '';
        detailedResultsDiv.innerHTML = '';
        resultsContainer.style.display = 'block';

        if (!results.errors || results.errors.length === 0) {
            summaryResultsDiv.innerHTML = '<div class="success-message">Проверка успешно завершена. Ошибок не найдено!</div>';
            return;
        }

        // 1. Aggregate errors by rule name
        const errorsByRule = results.errors.reduce((acc, error) => {
            const ruleName = error.rule_name;
            if (!acc[ruleName]) {
                acc[ruleName] = [];
            }
            acc[ruleName].push(error);
            return acc;
        }, {});

        // 2. Render summary table
        const summaryTable = document.createElement('table');
        summaryTable.className = 'results-table summary-table';
        summaryTable.innerHTML = `
            <thead>
                <tr>
                    <th>Название проверки</th>
                    <th>Количество ошибок</th>
                </tr>
            </thead>
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

        // 3. Add click listener for details
        summaryTable.querySelector('tbody').addEventListener('click', (event) => {
            const row = event.target.closest('.summary-row');
            if (!row) return;

            // Highlight selected row
            document.querySelectorAll('.summary-row').forEach(r => r.classList.remove('active'));
            row.classList.add('active');

            const ruleName = row.dataset.ruleName;
            const detailedErrors = errorsByRule[ruleName];
            renderDetailedTable(detailedErrors);
        });
    };

    const renderDetailedTable = (errors) => {
        const detailedResultsDiv = document.getElementById('detailed-results');
        detailedResultsDiv.innerHTML = ''; // Clear previous details

        if (!errors || errors.length === 0) return;

        const detailTable = document.createElement('table');
        detailTable.className = 'results-table detail-table';
        detailTable.innerHTML = `
            <caption>Детали по ошибкам для: "${errors[0].rule_name}"</caption>
            <thead>
                <tr>
                    <th>Строка</th>
                    <th>Колонка</th>
                    <th>Значение</th>
                </tr>
            </thead>
            <tbody>
                ${errors.map(e => `
                    <tr>
                        <td>${e.row}</td>
                        <td>${e.column}</td>
                        <td>${e.value}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        detailedResultsDiv.appendChild(detailTable);
    };

    const showTemplateSuggestions = (templates) => {
        templateSuggestionsList.innerHTML = '';
        templates.forEach(template => {
            const button = document.createElement('button');
            button.className = 'action-button';
            button.textContent = template.name;
            button.onclick = () => {
                appliedRules = JSON.parse(JSON.stringify(template.rules));
                templateSuggestionContainer.style.display = 'none';
                renderColumnsConfig();
            };
            templateSuggestionsList.appendChild(button);
        });
        templateSuggestionContainer.style.display = 'block';
    };

    // --- Event Handlers ---
    fileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        resetUI();
        fileLabel.textContent = file.name;
        loadingSpinner.style.display = 'block';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const uploadResponse = await fetch('/upload/', { method: 'POST', body: formData });
            const uploadData = await uploadResponse.json();
            if (!uploadResponse.ok) throw new Error(uploadData.detail || 'Failed to upload file');

            currentFileId = uploadData.fileId;
            currentColumns = uploadData.columns;

            // Initialize empty rules for all columns
            currentColumns.forEach(col => { appliedRules[col] = []; });

            const matchResponse = await fetch('/api/templates/find-matches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ columns: currentColumns })
            });
            const matchingTemplates = await matchResponse.json();

            if (matchingTemplates.length > 0) {
                showTemplateSuggestions(matchingTemplates);
            } else {
                renderColumnsConfig();
            }
        } catch (error) {
            showError(`Ошибка: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    });

    skipTemplatesBtn.addEventListener('click', () => {
        templateSuggestionContainer.style.display = 'none';
        renderColumnsConfig();
    });

    columnsListDiv.addEventListener('change', (event) => {
        if (event.target.classList.contains('rule-select')) {
            const selectedRuleId = event.target.value;
            if (!selectedRuleId) return;

            const columnName = event.target.closest('.column-config').querySelector('.column-name').textContent;
            if (!appliedRules[columnName].includes(selectedRuleId)) {
                appliedRules[columnName].push(selectedRuleId);
                renderAppliedRulesForColumn(columnName);
            }
            event.target.value = "";
        }
    });

    columnsListDiv.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-rule-btn')) {
            const { column, rule } = event.target.dataset;
            appliedRules[column] = appliedRules[column].filter(r => r !== rule);
            renderAppliedRulesForColumn(column);
        }
    });

    saveTemplateBtn.addEventListener('click', () => {
        templateNameInput.value = '';
        saveTemplateModal.style.display = 'flex';
        templateNameInput.focus();
    });

    cancelSaveBtn.addEventListener('click', () => {
        saveTemplateModal.style.display = 'none';
    });

    confirmSaveBtn.addEventListener('click', async () => {
        const templateName = templateNameInput.value.trim();
        if (!templateName) return showError("Имя шаблона не может быть пустым.");

        const payload = {
            name: templateName,
            columns: currentColumns,
            rules: appliedRules
        };

        confirmSaveBtn.disabled = true;
        confirmSaveBtn.textContent = 'Сохранение...';

        try {
            const response = await fetch('/api/templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to save template');

            saveTemplateModal.style.display = 'none';
            alert(`Шаблон "${templateName}" успешно сохранен!`);
        } catch (error) {
            showError(`Ошибка сохранения шаблона: ${error.message}`);
        } finally {
            confirmSaveBtn.disabled = false;
            confirmSaveBtn.textContent = 'Сохранить';
        }
    });

    validateButton.addEventListener('click', async () => {
        if (!currentFileId) return showError("Нет файла для проверки.");

        loadingSpinner.style.display = 'block';
        resultsContainer.style.display = 'none';

        try {
            const response = await fetch('/api/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fileId: currentFileId, rules: appliedRules })
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

    // --- Initial Load ---
    fetchAvailableRules();
});