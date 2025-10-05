document.addEventListener('DOMContentLoaded', () => {
    // --- 1. DOM Elements ---
    const loadingSpinner = document.getElementById('loading');
    const fileInput = document.getElementById('fileInput');
    const fileLabel = document.querySelector('.file-label');
    const columnsConfigContainer = document.getElementById('columns-config-container');
    const columnsListDiv = document.getElementById('columns-list');
    const validateButton = document.getElementById('validateButton');
    const resultsContainer = document.getElementById('validation-results-container');
    const summaryResultsDiv = document.getElementById('summary-results');
    const detailedResultsDiv = document.getElementById('detailed-results');
    const sheetSelectModal = document.getElementById('sheet-select-modal');
    const sheetListDiv = document.getElementById('sheet-list');
    const projectNameHeader = document.getElementById('project-name-header');
    const notificationToast = document.getElementById('notification-toast');

    // --- 2. Application State ---
    const projectId = window.location.pathname.split('/').pop();
    let currentFileId = null;
    let currentSheetName = null;
    let currentColumns = [];
    let availableRules = [];
    let appliedRules = {};

    // --- 3. Helper Functions ---
    const showNotification = (message, type = 'success') => {
        notificationToast.textContent = message;
        notificationToast.className = `toast show ${type}`;
        setTimeout(() => { notificationToast.className = notificationToast.className.replace('show', ''); }, 3000);
    };
    const showError = (message) => showNotification(message, 'error');

    const formatRuleDisplayName = (ruleDef, ruleConfig) => {
        if (ruleDef.is_configurable && ruleConfig.params) {
            const paramsString = Object.entries(ruleConfig.params).map(([k, v]) => `${k}: ${v}`).join(', ');
            return `${ruleDef.name} (${paramsString})`;
        }
        return ruleDef.name;
    };

    const resetUI = (isNewFile = true) => {
        columnsConfigContainer.style.display = 'none';
        resultsContainer.style.display = 'none';
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

    // --- 4. UI Rendering ---
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
        if (!appliedRules[columnName] || !appliedRules[columnName].rules) return;

        appliedRules[columnName].rules.forEach((ruleConfig, index) => {
            const ruleDef = availableRules.find(r => r.id === ruleConfig.id);
            if (!ruleDef) return;
            const ruleDisplayName = formatRuleDisplayName(ruleDef, ruleConfig);
            const ruleTag = document.createElement('div');
            ruleTag.className = 'rule-tag';
            ruleTag.innerHTML = `<span>${ruleDisplayName}</span><button class="remove-rule-btn" data-column="${columnName}" data-index="${index}">&times;</button>`;
            container.appendChild(ruleTag);
        });
    };

    const renderValidationResults = (results) => {
        // ... (This function remains largely the same as before)
        const goldenRecordStatsDiv = document.getElementById('golden-record-stats');
        summaryResultsDiv.innerHTML = '';
        detailedResultsDiv.innerHTML = '';
        resultsContainer.style.display = 'block';

        const totalRows = results.total_rows || 0;
        const errorRowsCount = results.error_rows_count || 0;
        const errorPercentage = totalRows > 0 ? ((errorRowsCount / totalRows) * 100).toFixed(2) : 0;

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

        const errorsByRule = results.errors.reduce((acc, error) => {
            if (!acc[error.rule_name]) acc[error.rule_name] = [];
            acc[error.rule_name].push(error);
            return acc;
        }, {});

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

        summaryTable.querySelector('tbody').addEventListener('click', (event) => {
            const row = event.target.closest('.summary-row');
            if (!row) return;
            document.querySelectorAll('.summary-row').forEach(r => r.classList.remove('active'));
            row.classList.add('active');
            renderDetailedTable(errorsByRule[row.dataset.ruleName]);
        });
    };

    const renderDetailedTable = (errors) => {
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

    // --- 5. Core Logic ---
    const fetchAvailableRules = async () => {
        try {
            const response = await fetch('/api/rules');
            if (!response.ok) throw new Error('Failed to fetch rules');
            availableRules = await response.json();
        } catch (error) {
            showError(`Ошибка загрузки правил: ${error.message}`);
        }
    };

    const handleSheetSelection = async (sheetName) => {
        currentSheetName = sheetName;
        sheetSelectModal.style.display = 'none';
        loadingSpinner.style.display = 'block';
        try {
            const response = await fetch(`/api/projects/${projectId}/select-sheet`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fileId: currentFileId, sheetName: currentSheetName })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to select sheet');
            currentColumns = data.columns;
            // Initialize rules for columns if not already present
            currentColumns.forEach(col => {
                if (!appliedRules[col]) appliedRules[col] = { is_required: false, rules: [] };
            });
            renderColumnsConfig();
        } catch (error) {
            showError(`Ошибка выбора листа: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

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

    const fetchProjectDetails = async () => {
        loadingSpinner.style.display = 'block';
        try {
            const response = await fetch(`/api/projects/${projectId}`);
            if (!response.ok) throw new Error((await response.json()).detail);
            const project = await response.json();

            projectNameHeader.textContent = `Проект: ${project.name}`;
            document.title = `${project.name} - DQMaster`;
            appliedRules = project.rules || {};

            if (project.files && project.files.length > 0) {
                const file = project.files[0];
                currentFileId = file.id;
                fileLabel.textContent = file.original_name;
                // If there's a file, we need its columns to render the config
                // We'll just pick the first sheet by default for now
                if (file.sheets && file.sheets.length > 0) {
                    await handleSheetSelection(file.sheets[0]);
                }
            }
        } catch (error) {
            projectNameHeader.textContent = 'Ошибка загрузки проекта';
            showError(error.message);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

    // --- 6. Event Handlers ---
    fileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        resetUI();
        loadingSpinner.style.display = 'block';
        fileLabel.textContent = file.name;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`/api/projects/${projectId}/upload`, {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'File upload failed');

            currentFileId = data.id;
            if (data.sheets && data.sheets.length > 1) {
                showSheetSelectionModal(data.sheets);
            } else if (data.sheets && data.sheets.length === 1) {
                await handleSheetSelection(data.sheets[0]);
            } else {
                throw new Error('No sheets found in the uploaded file.');
            }
        } catch (error) {
            showError(`Ошибка загрузки: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
            fileInput.value = '';
        }
    });

    validateButton.addEventListener('click', async () => {
        if (!currentFileId || !currentSheetName) return showError("Файл или лист не выбраны для проверки.");
        loadingSpinner.style.display = 'block';
        resultsContainer.style.display = 'none';
        try {
            const payload = { fileId: currentFileId, sheetName: currentSheetName, rules: appliedRules };
            const response = await fetch(`/api/projects/${projectId}/validate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const results = await response.json();
            if (!response.ok) throw new Error(results.detail || 'Validation failed');
            renderValidationResults(results);
            showNotification('Проверка завершена. Конфигурация правил сохранена.', 'success');
        } catch (error) {
            showError(`Ошибка проверки: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    });

    columnsListDiv.addEventListener('change', (event) => {
        const target = event.target;
        if (target.classList.contains('required-checkbox')) {
            const column = target.dataset.column;
            appliedRules[column].is_required = target.checked;
        } else if (target.classList.contains('rule-select')) {
            const selectedRuleId = target.value;
            if (!selectedRuleId) return;
            const columnName = target.closest('.column-config').querySelector('.column-name').textContent;
            const newRule = { id: selectedRuleId, params: null };
            if (!appliedRules[columnName].rules.some(r => JSON.stringify(r) === JSON.stringify(newRule))) {
                appliedRules[columnName].rules.push(newRule);
                renderAppliedRulesForColumn(columnName);
            } else {
                showNotification('Это правило уже добавлено.', 'error');
            }
            target.value = "";
        }
    });

    columnsListDiv.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-rule-btn')) {
            const { column, index } = event.target.dataset;
            appliedRules[column].rules.splice(index, 1);
            renderAppliedRulesForColumn(column);
        }
    });

    // --- 7. Initial Load ---
    const initialize = async () => {
        // First, ensure all static data like rules is available.
        await fetchAvailableRules();
        // Then, fetch the project-specific details which may depend on the rules.
        await fetchProjectDetails();
    };

    initialize();
});