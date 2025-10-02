document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const fileInput = document.getElementById('fileInput');
    const fileLabel = document.querySelector('.file-label');
    const loadingSpinner = document.getElementById('loading');
    const columnsConfigContainer = document.getElementById('columns-config-container');
    const columnsListDiv = document.getElementById('columns-list');
    const validateButton = document.getElementById('validateButton');
    const resultsContainer = document.getElementById('validation-results-container');
    const resultsOutputDiv = document.getElementById('results-output');
    const errorContainer = document.getElementById('error-container');

    // --- Application State ---
    let currentFileId = null;
    let availableRules = [];
    let appliedRules = {}; // Structure: { "columnName": ["rule_id_1", "rule_id_2"] }

    // --- Helper Functions ---
    const resetUI = () => {
        columnsConfigContainer.style.display = 'none';
        resultsContainer.style.display = 'none';
        errorContainer.style.display = 'none';
        columnsListDiv.innerHTML = '';
        resultsOutputDiv.innerHTML = '';
        errorContainer.textContent = '';
        fileLabel.textContent = 'Выберите файл...';
        appliedRules = {};
        currentFileId = null;
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

    // --- UI Rendering ---
    const renderColumnsConfig = (columns) => {
        columnsListDiv.innerHTML = '';
        columns.forEach(column => {
            appliedRules[column] = []; // Initialize empty rules for each column
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
        });
        columnsConfigContainer.style.display = 'block';
    };

    const renderAppliedRulesForColumn = (columnName) => {
        const container = document.getElementById(`rules-for-${columnName}`);
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

    const showError = (message) => {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
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
            const response = await fetch('/upload/', { method: 'POST', body: formData });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to upload file');
            }

            currentFileId = data.fileId;
            renderColumnsConfig(data.columns);

        } catch (error) {
            showError(`Ошибка загрузки: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    });

    columnsListDiv.addEventListener('change', (event) => {
        if (event.target.classList.contains('rule-select')) {
            const selectedRuleId = event.target.value;
            if (!selectedRuleId) return;

            const columnDiv = event.target.closest('.column-config');
            const columnName = columnDiv.querySelector('.column-name').textContent;

            // Add rule only if it's not already applied
            if (!appliedRules[columnName].includes(selectedRuleId)) {
                appliedRules[columnName].push(selectedRuleId);
                renderAppliedRulesForColumn(columnName);
            }

            event.target.value = ""; // Reset dropdown
        }
    });

    columnsListDiv.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-rule-btn')) {
            const { column, rule } = event.target.dataset;
            appliedRules[column] = appliedRules[column].filter(r => r !== rule);
            renderAppliedRulesForColumn(column);
        }
    });

    validateButton.addEventListener('click', async () => {
        if (!currentFileId) {
            showError("Нет загруженного файла для проверки.");
            return;
        }

        loadingSpinner.style.display = 'block';
        resultsContainer.style.display = 'none';
        resultsOutputDiv.innerHTML = '';

        const payload = {
            fileId: currentFileId,
            rules: appliedRules
        };

        try {
            const response = await fetch('/api/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const results = await response.json();
            if (!response.ok) {
                throw new Error(results.detail || 'Validation request failed');
            }
            renderValidationResults(results);

        } catch (error) {
            showError(`Ошибка проверки: ${error.message}`);
        } finally {
            loadingSpinner.style.display = 'none';
        }
    });


    const renderValidationResults = (results) => {
        resultsOutputDiv.innerHTML = ''; // Clear previous results
        resultsContainer.style.display = 'block';

        if (results.errors && results.errors.length > 0) {
            const errors = results.errors;
            const table = document.createElement('table');
            table.className = 'results-table';
            table.innerHTML = `
                <thead>
                    <tr>
                        <th>Строка</th>
                        <th>Колонка</th>
                        <th>Значение</th>
                        <th>Нарушенное правило</th>
                    </tr>
                </thead>
                <tbody>
                    ${errors.map(error => `
                        <tr>
                            <td>${error.row}</td>
                            <td>${error.column}</td>
                            <td>${error.value}</td>
                            <td>${error.rule_name}</td>
                        </tr>
                    `).join('')}
                </tbody>
            `;
            resultsOutputDiv.appendChild(table);
        } else {
            resultsOutputDiv.innerHTML = '<div class="success-message">Проверка успешно завершена. Ошибок не найдено!</div>';
        }
    };

    // --- Initial Load ---
    fetchAvailableRules();
});