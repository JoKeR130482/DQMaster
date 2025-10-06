document.addEventListener('DOMContentLoaded', () => {

    // --- 1. STATE & CONSTANTS ---
    const projectId = window.location.pathname.split('/').pop();
    let projectData = {};
    let availableRules = [];

    // --- 2. DOM ELEMENTS ---
    const dom = {
        loading: document.getElementById('loading'),
        errorContainer: document.getElementById('error-container'),
        projectNameHeader: document.getElementById('project-name-header'),
        notificationToast: document.getElementById('notification-toast'),
        // Sections
        uploadSection: document.getElementById('upload-section'),
        sheetSelectionContainer: document.getElementById('sheet-selection-container'),
        rulesAndValidationContainer: document.getElementById('rules-and-validation-container'),
        validationResultsContainer: document.getElementById('validation-results-container'),
        // File UI
        fileUploadBox: document.getElementById('file-upload-box'),
        fileInput: document.getElementById('fileInput'),
        fileDisplayContainer: document.getElementById('file-display-container'),
        fileNameDisplay: document.getElementById('file-name-display'),
        deleteFileBtn: document.getElementById('delete-file-btn'),
        // Sheet UI
        sheetList: document.getElementById('sheet-list'),
        // Rules & Validation UI
        selectedSheetDisplay: document.getElementById('selected-sheet-display'),
        columnsList: document.getElementById('columns-list'),
        validateButton: document.getElementById('validateButton'),
        // Results UI
        goldenRecordStats: document.getElementById('golden-record-stats'),
        summaryResults: document.getElementById('summary-results'),
        detailedResults: document.getElementById('detailed-results'),
        runAnotherValidationBtn: document.getElementById('run-another-validation-btn'),
        // Rule Config Modal
        ruleConfigModal: document.getElementById('rule-config-modal'),
        ruleConfigTitle: document.getElementById('rule-config-title'),
        ruleConfigForm: document.getElementById('rule-config-form'),
        cancelRuleConfigBtn: document.getElementById('cancel-rule-config-btn'),
        confirmRuleConfigBtn: document.getElementById('confirm-rule-config-btn'),
    };

    // --- 3. API HELPERS ---
    const api = {
        getProject: () => fetch(`/api/projects/${projectId}`),
        getRules: () => fetch('/api/rules'),
        uploadFile: (formData) => fetch(`/api/projects/${projectId}/upload`, { method: 'POST', body: formData }),
        deleteFile: () => fetch(`/api/projects/${projectId}/file`, { method: 'DELETE' }),
        selectSheet: (fileId, sheetName) => fetch(`/api/projects/${projectId}/select-sheet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fileId, sheetName }),
        }),
        validate: (fileId, sheetName, rules) => fetch(`/api/projects/${projectId}/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fileId, sheetName, rules }),
        }),
    };

    // --- 4. UI RENDERING ---

    const showNotification = (message, type = 'success') => {
        dom.notificationToast.textContent = message;
        dom.notificationToast.className = `toast show ${type}`;
        setTimeout(() => { dom.notificationToast.className = dom.notificationToast.className.replace('show', ''); }, 3000);
    };

    const showError = (message) => {
        dom.errorContainer.textContent = message;
        dom.errorContainer.style.display = 'block';
    };

    const render = () => {
        dom.projectNameHeader.textContent = `Проект: ${projectData.name}`;
        document.title = `${projectData.name} - DQMaster`;

        // Hide all major sections initially
        dom.uploadSection.style.display = 'none';
        dom.sheetSelectionContainer.style.display = 'none';
        dom.rulesAndValidationContainer.style.display = 'none';
        dom.validationResultsContainer.style.display = 'none';

        if (!projectData.files || projectData.files.length === 0) {
            // State 1: No file uploaded
            dom.uploadSection.style.display = 'block';
            dom.fileUploadBox.style.display = 'block';
            dom.fileDisplayContainer.style.display = 'none';
        } else {
            // State 2: File is present
            const file = projectData.files[0];
            dom.uploadSection.style.display = 'block';
            dom.fileUploadBox.style.display = 'none';
            dom.fileDisplayContainer.style.display = 'block';
            dom.fileNameDisplay.textContent = file.original_name;

            if (!projectData.selected_sheet) {
                // State 2a: Sheet not selected yet
                dom.sheetSelectionContainer.style.display = 'block';
                renderSheetSelection(file.sheets);
            } else {
                // State 2b: Sheet is selected, show rules config
                dom.rulesAndValidationContainer.style.display = 'block';
                dom.selectedSheetDisplay.textContent = projectData.selected_sheet;
                renderColumnsConfig(projectData.columns, projectData.rules);
            }
        }
    };

    const renderSheetSelection = (sheets) => {
        dom.sheetList.innerHTML = '';
        sheets.forEach(sheetName => {
            const button = document.createElement('button');
            button.className = 'sheet-select-btn action-button';
            button.textContent = sheetName;
            button.dataset.sheetName = sheetName;
            dom.sheetList.appendChild(button);
        });
    };

    const renderColumnsConfig = (columns, rules) => {
        dom.columnsList.innerHTML = '';
        if (!columns) return;

        columns.forEach(column => {
            const columnRules = rules[column] || { is_required: false, rules: [] };
            const isChecked = columnRules.is_required ? 'checked' : '';

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
                        <select class="rule-select" data-column="${column}">
                            <option value="">-- Добавить правило --</option>
                            ${availableRules.map(rule => `<option value="${rule.id}">${rule.name}</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="applied-rules-container" id="rules-for-${column}"></div>
            `;
            dom.columnsList.appendChild(columnDiv);
            renderAppliedRulesForColumn(column);
        });
    };

    const formatRuleDisplayName = (ruleId, params) => {
        const ruleDef = availableRules.find(r => r.id === ruleId);
        if (!ruleDef) return `Неизвестное правило: ${ruleId}`;
        if (ruleDef.is_configurable && params) {
            const paramsString = Object.entries(params).map(([k, v]) => `${k}: ${v}`).join(', ');
            return `${ruleDef.name} (${paramsString})`;
        }
        return ruleDef.name;
    };

    const renderAppliedRulesForColumn = (columnName) => {
        const container = document.getElementById(`rules-for-${columnName}`);
        if (!container) return;
        container.innerHTML = '';
        const columnRules = projectData.rules[columnName];
        if (!columnRules || !columnRules.rules) return;

        columnRules.rules.forEach((ruleConfig, index) => {
            const ruleDisplayName = formatRuleDisplayName(ruleConfig.id, ruleConfig.params);
            const ruleTag = document.createElement('div');
            ruleTag.className = 'rule-tag';
            ruleTag.innerHTML = `<span>${ruleDisplayName}</span><button class="remove-rule-btn" data-column="${columnName}" data-index="${index}">&times;</button>`;
            container.appendChild(ruleTag);
        });
    };

    const renderValidationResults = (results) => {
        dom.validationResultsContainer.style.display = 'block';
        dom.rulesAndValidationContainer.style.display = 'none'; // Hide config
        dom.summaryResults.innerHTML = '';
        dom.detailedResults.innerHTML = '';

        const { total_rows = 0, error_rows_count = 0, errors = [] } = results;
        const errorPercentage = total_rows > 0 ? ((error_rows_count / total_rows) * 100).toFixed(2) : 0;

        dom.goldenRecordStats.innerHTML = `
            <div class="stats-summary">
                <span>Всего строк: <strong>${total_rows}</strong></span>
                <span>Строк с ошибками: <strong>${error_rows_count}</strong></span>
                <span>Процент ошибочных строк: <strong>${errorPercentage}%</strong></span>
            </div>
        `;

        if (errors.length === 0) {
            dom.summaryResults.innerHTML = '<div class="success-message">Проверка успешно завершена. Ошибок не найдено!</div>';
            return;
        }

        const errorsByRule = errors.reduce((acc, error) => {
            if (!acc[error.rule_name]) acc[error.rule_name] = [];
            acc[error.rule_name].push(error);
            return acc;
        }, {});

        const summaryTable = document.createElement('table');
        summaryTable.className = 'results-table summary-table';
        summaryTable.innerHTML = `
            <thead><tr><th>Правило</th><th>Количество ошибок</th></tr></thead>
            <tbody>
                ${Object.entries(errorsByRule).map(([ruleName, ruleErrors]) => `
                    <tr class="summary-row" data-rule-name="${ruleName}">
                        <td>${ruleName}</td>
                        <td>${ruleErrors.length}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;
        dom.summaryResults.appendChild(summaryTable);
    };

    const renderDetailedTable = (errors) => {
        dom.detailedResults.innerHTML = '';
        if (!errors || errors.length === 0) return;
        const detailTable = document.createElement('table');
        detailTable.className = 'results-table detail-table';
        detailTable.innerHTML = `
            <caption>Детали по ошибкам для: "${errors[0].rule_name}"</caption>
            <thead><tr><th>Строка</th><th>Колонка</th><th>Значение</th></tr></thead>
            <tbody>
                ${errors.map(e => `<tr><td>${e.row}</td><td>${e.column}</td><td>${e.value || ''}</td></tr>`).join('')}
            </tbody>
        `;
        dom.detailedResults.appendChild(detailTable);
    };

    // --- 5. EVENT HANDLERS ---
    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        dom.loading.style.display = 'block';
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await api.uploadFile(formData);
            if (!response.ok) throw new Error((await response.json()).detail);
            await init(); // Re-initialize the whole state
            showNotification("Файл успешно загружен.");
        } catch (error) {
            showError(`Ошибка загрузки: ${error.message}`);
        } finally {
            dom.loading.style.display = 'none';
            dom.fileInput.value = '';
        }
    };

    const handleDeleteFile = async () => {
        if (!confirm("Вы уверены? Все настроенные правила для этого файла будут удалены.")) return;
        dom.loading.style.display = 'block';
        try {
            const response = await api.deleteFile();
            if (!response.ok) throw new Error((await response.json()).detail);
            projectData = await response.json();
            render();
            showNotification("Файл удален.");
        } catch (error) {
            showError(`Ошибка удаления файла: ${error.message}`);
        } finally {
            dom.loading.style.display = 'none';
        }
    };

    const handleSheetSelect = async (event) => {
        if (!event.target.matches('.sheet-select-btn')) return;
        const sheetName = event.target.dataset.sheetName;
        dom.loading.style.display = 'block';
        try {
            const fileId = projectData.files[0].id;
            const response = await api.selectSheet(fileId, sheetName);
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail);

            projectData.selected_sheet = sheetName;
            projectData.columns = data.columns;
            projectData.rules = data.rules; // Load existing rules for this sheet
            render();
        } catch (error) {
            showError(`Ошибка выбора листа: ${error.message}`);
        } finally {
            dom.loading.style.display = 'none';
        }
    };

    const handleRulesConfigChange = (event) => {
        const target = event.target;
        const column = target.dataset.column;
        if (!column) return;

        if (!projectData.rules[column]) {
            projectData.rules[column] = { is_required: false, rules: [] };
        }

        if (target.matches('.required-checkbox')) {
            projectData.rules[column].is_required = target.checked;
        } else if (target.matches('.rule-select')) {
            const ruleId = target.value;
            if (!ruleId) return;
            const newRule = { id: ruleId, params: null }; // Params to be added via modal
            if (!projectData.rules[column].rules.some(r => r.id === ruleId)) {
                projectData.rules[column].rules.push(newRule);
                renderAppliedRulesForColumn(column);
            } else {
                showNotification('Это правило уже добавлено.', 'error');
            }
            target.value = ""; // Reset select
        }
    };

    const handleRulesContainerClick = (event) => {
        if (event.target.matches('.remove-rule-btn')) {
            const { column, index } = event.target.dataset;
            projectData.rules[column].rules.splice(index, 1);
            renderAppliedRulesForColumn(column);
        }
    };

    const handleValidate = async () => {
        const fileId = projectData.files[0].id;
        const sheetName = projectData.selected_sheet;
        if (!fileId || !sheetName) return showError("Файл или лист не выбраны.");

        dom.loading.style.display = 'block';
        try {
            const response = await api.validate(fileId, sheetName, projectData.rules);
            const results = await response.json();
            if (!response.ok) throw new Error(results.detail);
            renderValidationResults(results);
            showNotification('Проверка завершена. Конфигурация правил сохранена.', 'success');
        } catch (error) {
            showError(`Ошибка проверки: ${error.message}`);
        } finally {
            dom.loading.style.display = 'none';
        }
    };

    const handleSummaryTableClick = (event) => {
        const row = event.target.closest('.summary-row');
        if (!row) return;

        document.querySelectorAll('.summary-row').forEach(r => r.classList.remove('active'));
        row.classList.add('active');

        const ruleName = row.dataset.ruleName;
        // This is inefficient, but works for now. We need to re-fetch the full results.
        // A better approach would be to store the full results in state.
        api.validate(projectData.files[0].id, projectData.selected_sheet, projectData.rules)
            .then(res => res.json())
            .then(results => {
                const errorsForRule = results.errors.filter(e => e.rule_name === ruleName);
                renderDetailedTable(errorsForRule);
            });
    };

    // --- 6. INITIALIZATION ---
    const init = async () => {
        dom.loading.style.display = 'block';
        try {
            const [rulesResponse, projectResponse] = await Promise.all([api.getRules(), api.getProject()]);
            if (!rulesResponse.ok) throw new Error('Не удалось загрузить библиотеку правил.');
            if (!projectResponse.ok) throw new Error('Не удалось загрузить данные проекта.');

            availableRules = await rulesResponse.json();
            projectData = await projectResponse.json();

            // The API for select-sheet now returns columns, so we need to get them if a sheet is pre-selected
            if (projectData.files.length > 0 && projectData.selected_sheet) {
                const fileId = projectData.files[0].id;
                const sheetName = projectData.selected_sheet;
                const sheetResponse = await api.selectSheet(fileId, sheetName);
                const sheetData = await sheetResponse.json();
                if (!sheetResponse.ok) throw new Error(sheetData.detail);
                projectData.columns = sheetData.columns;
                // The rules are already in projectData, no need to re-assign
            }

            render();
        } catch (error) {
            showError(error.message);
            dom.projectNameHeader.textContent = 'Ошибка';
        } finally {
            dom.loading.style.display = 'none';
        }
    };

    // Bind event listeners
    dom.fileInput.addEventListener('change', handleFileChange);
    dom.deleteFileBtn.addEventListener('click', handleDeleteFile);
    dom.sheetList.addEventListener('click', handleSheetSelect);
    dom.columnsList.addEventListener('change', handleRulesConfigChange);
    dom.columnsList.addEventListener('click', handleRulesContainerClick);
    dom.validateButton.addEventListener('click', handleValidate);
    dom.summaryResults.addEventListener('click', handleSummaryTableClick);
    dom.runAnotherValidationBtn.addEventListener('click', () => {
        dom.validationResultsContainer.style.display = 'none';
        dom.rulesAndValidationContainer.style.display = 'block';
    });

    init();
});