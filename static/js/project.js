document.addEventListener('DOMContentLoaded', () => {
    // --- 1. STATE & CONSTANTS ---
    const projectId = window.location.pathname.split('/').pop();
    let validationPollingId = null;
    let state = {
        project: null,
        availableRules: [],
        availableGroups: [],
        isLoading: true,
        error: null,
        showUploadForm: false,
        selectedSheetId: null,
        validationResults: null,
        isRuleModalOpen: false,
        editingRuleContext: null, // { fileId, sheetId, fieldId, ruleId? }
        showRequiredErrorsDetails: false,
        activeRuleDetailsKey: null, // e.g., "fileIdx-sheetIdx-ruleIdx"
    };

    // --- 2. DOM ELEMENTS ---
    const dom = {
        loading: document.getElementById('loading'),
        errorContainer: document.getElementById('error-container'),
        projectNameHeader: document.getElementById('project-name-header'),
        saveProjectBtn: document.getElementById('save-project-btn'),
        validateBtn: document.getElementById('validate-btn'),
        showUploadFormBtn: document.getElementById('show-upload-form-btn'),
        uploadFormContainer: document.getElementById('upload-form-container'),
        fileInput: document.getElementById('file-input'),
        cancelUploadBtn: document.getElementById('cancel-upload-btn'),
        importProgressContainer: document.getElementById('import-progress-container'),
        filesListContainer: document.getElementById('files-list-container'),
        progressContainer: document.getElementById('validation-progress-container'),
        resultsContainer: document.getElementById('validation-results-container'),
        goldenRecordStats: document.getElementById('golden-record-stats'),
        summaryResults: document.getElementById('summary-results'),
        detailedResults: document.getElementById('detailed-results'),
        notificationToast: document.getElementById('notification-toast'),
        // Rule Editor Modal
        ruleEditorModal: document.getElementById('rule-editor-modal'),
        ruleModalTitle: document.getElementById('rule-modal-title'),
        closeRuleModalBtn: document.getElementById('close-rule-modal-btn'),
        ruleEditorForm: document.getElementById('rule-editor-form'),
        cancelRuleModalBtn: document.getElementById('cancel-rule-modal-btn'),
        saveRuleBtn: document.getElementById('save-rule-btn'),
        autoRevalidateToggle: document.getElementById('auto-revalidate-toggle'),
    };

    // --- 3. API HELPERS ---
    const api = {
        getProject: () => fetch(`/api/projects/${projectId}`),
        getRules: () => fetch('/api/rules'),
        getRuleGroups: () => fetch('/api/rule-groups'),
        saveProject: (projectData) => fetch(`/api/projects/${projectId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(projectData),
        }),
        uploadFile: (formData) => fetch(`/api/projects/${projectId}/upload`, {
            method: 'POST',
            body: formData,
        }),
        validate: () => fetch(`/api/projects/${projectId}/validate`, { method: 'POST' }),
        getResults: () => fetch(`/api/projects/${projectId}/results`),
    };

    // --- 4. UTILS ---
    const showNotification = (message, type = 'success') => {
        dom.notificationToast.textContent = message;
        dom.notificationToast.className = `toast ${type} show`;
        setTimeout(() => { dom.notificationToast.className = dom.notificationToast.className.replace('show', ''); }, 3000);
    };
    const showError = (message) => {
        dom.errorContainer.textContent = message;
        dom.errorContainer.style.display = 'block';
    };
    const newId = () => 'id_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 10);

    const escapeHTML = (str) => {
        if (typeof str !== 'string') return str;
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    };

    function highlightMisspelledWords(escapedText, errors) {
        if (!Array.isArray(errors) || errors.length === 0) {
            return escapedText;
        }
        const escapedErrors = errors.map(e =>
            String(e).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        );
        // Используем Unicode-совместимые границы слов:
        // (?<!\p{L}) — отрицательный просмотр назад: не буква перед
        // (?!\p{L})  — отрицательный просмотр вперёд: не буква после
        // Флаг 'u' обязателен для поддержки \p{L}
        const pattern = `(?<!\\p{L})(${escapedErrors.join('|')})(?!\\p{L})`;
        const errorsRegex = new RegExp(pattern, 'gui');

        return escapedText.replace(errorsRegex, (match) =>
            `<span class="misspelled-word" title="Двойной клик — добавить в словарь">${match}</span>`
        );
    }


    // --- 5. RENDER FUNCTIONS ---
    function render() {
        dom.loading.style.display = state.isLoading ? 'block' : 'none';
        dom.errorContainer.style.display = state.error ? 'block' : 'none';
        if (state.error) dom.errorContainer.textContent = state.error;

        // Render modal based on state
        dom.ruleEditorModal.style.display = state.isRuleModalOpen ? 'flex' : 'none';
        if (state.isRuleModalOpen) {
            renderRuleEditor();
        }

        if (!state.project) return;

        dom.autoRevalidateToggle.checked = state.project.auto_revalidate ?? true;

        dom.projectNameHeader.innerHTML = `
            <div>
                ${state.project.name}
                <div class="entity-id">ID: ${state.project.id}</div>
            </div>`;
        dom.uploadFormContainer.style.display = state.showUploadForm ? 'flex' : 'none';

        renderFiles();
        lucide.createIcons();
    }

    function renderFiles() {
        dom.filesListContainer.innerHTML = '';
        if (!state.project.files) return;

        state.project.files.forEach(file => {
            const fileCard = document.createElement('div');
            fileCard.className = 'file-card';
            fileCard.dataset.fileId = file.id;

            const totalFields = file.sheets.reduce((acc, sheet) => acc + sheet.fields.length, 0);

            fileCard.innerHTML = `
                <div class="file-header">
                    <div class="file-name-wrapper">
                        <h3 class="file-name">${file.name}</h3>
                        <div class="entity-id">ID: ${file.id}</div>
                    </div>
                    <div class="file-actions">
                        <button class="btn btn-secondary reimport-file-btn" title="Переимпортировать данные из исходного файла" style="display:none;">
                            <i data-lucide="refresh-cw"></i>
                        </button>
                        <button class="btn btn-icon danger remove-file-btn" title="Удалить файл">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                </div>

                <div class="import-metadata">
                    <h5>Метаданные импорта</h5>
                    <div class="metadata-grid">
                        <div class="metadata-item"><strong>Исходное имя:</strong> <span>${file.name}</span></div>
                        <div class="metadata-item"><strong>Сохраненное имя:</strong> <span>${file.saved_name}</span></div>
                        <div class="metadata-item"><strong>Кол-во листов:</strong> <span>${file.sheets.length}</span></div>
                        <div class="metadata-item"><strong>Кол-во полей:</strong> <span>${totalFields}</span></div>
                    </div>
                </div>

                <div class="sheets-list"></div>
            `;
            const sheetsList = fileCard.querySelector('.sheets-list');
            file.sheets.forEach(sheet => sheetsList.appendChild(renderSheet(file.id, sheet)));
            dom.filesListContainer.appendChild(fileCard);
        });
    }

    function renderSheet(fileId, sheet) {
        const sheetItem = document.createElement('div');
        sheetItem.className = 'sheet-item';
        sheetItem.dataset.sheetId = sheet.id;
        sheetItem.innerHTML = `
            <label><input type="checkbox" class="toggle-sheet-active" ${sheet.is_active ? 'checked' : ''}><span class="sheet-name">${sheet.name}</span></label>
            <button class="configure-sheet-btn">${state.selectedSheetId === sheet.id ? 'Скрыть настройки' : 'Настроить поля'}</button>
        `;
        if (state.selectedSheetId === sheet.id) {
            sheetItem.appendChild(renderFieldsConfig(fileId, sheet));
        }
        return sheetItem;
    }

    function renderFieldsConfig(fileId, sheet) {
        const configContainer = document.createElement('div');
        configContainer.className = 'fields-config-container';
        configContainer.innerHTML = `
            <h5>Поля листа "${sheet.name}"</h5>
            <div class="fields-list"></div>
            `;
        const fieldsList = configContainer.querySelector('.fields-list');
        sheet.fields.forEach(field => fieldsList.appendChild(renderField(fileId, sheet.id, field)));
        return configContainer;
    }

    function renderField(fileId, sheetId, field) {
        const fieldCard = document.createElement('div');
        fieldCard.className = 'field-card';
        fieldCard.dataset.fieldId = field.id;
        fieldCard.innerHTML = `
            <div class="field-header">
                <span class="field-name">${field.name}</span>
                <div class="field-actions">
                    <label><input type="checkbox" class="toggle-field-required" ${field.is_required ? 'checked' : ''}><span class="text-sm">Обязательное</span></label>
                </div>
            </div>
            <div class="rules-list"></div>
            <div class="add-rule-container">
                <button class="btn btn-secondary add-rule-btn"><i data-lucide="plus"></i> Добавить правило</button>
            </div>`;
        const rulesList = fieldCard.querySelector('.rules-list');
        const sortedRules = [...field.rules].sort((a, b) => a.order - b.order);
        sortedRules.forEach(rule => rulesList.appendChild(renderRule(rule)));
        return fieldCard;
    }

    function renderRule(rule) {
        const ruleItem = document.createElement('div');
        ruleItem.className = 'rule-item';
        ruleItem.dataset.ruleId = rule.id;

        const displayName = formatRuleName(rule);

        ruleItem.innerHTML = `
            <span class="rule-name">${displayName}</span>
            <div class="rule-actions">
                <button class="btn btn-icon edit-rule-btn" title="Изменить правило"><i data-lucide="settings-2"></i></button>
                <button class="btn btn-icon move-rule-up-btn" title="Переместить вверх"><i data-lucide="arrow-up"></i></button>
                <button class="btn btn-icon move-rule-down-btn" title="Переместить вниз"><i data-lucide="arrow-down"></i></button>
                <button class="btn btn-icon danger remove-rule-btn" title="Удалить правило"><i data-lucide="trash-2"></i></button>
            </div>`;
        return ruleItem;
    }

    function formatRuleName(rule) {
        if (rule.group_id) {
            const group = state.availableGroups.find(g => g.id === rule.group_id);
            return group ? `Группа: ${group.name}` : `Неизвестная группа: ${rule.group_id}`;
        }

        const ruleDef = state.availableRules.find(r => r.id === rule.type);
        if (!ruleDef) return rule.type;

        // Specific formatter for substring_check
        if (rule.type === 'substring_check' && rule.params) {
            const { value, mode = 'contains', case_sensitive = false } = rule.params;
            if (!value) return ruleDef.name;
            const mode_text = mode === 'not_contains' ? 'не содержит' : 'содержит';
            const case_text = case_sensitive ? " (регистр важен)" : "";
            return `Подстрока '${value}' (${mode_text}${case_text})`;
        }

        // Generic fallback for other rules that might have been configured
        if (rule.params && rule.params.value) {
             return `${ruleDef.name}: ${rule.params.value}`;
        }

        // Backward compatibility for old format
        if (rule.value) {
            return `${ruleDef.name}: ${rule.value}`;
        }

        return ruleDef.name;
    }

    function renderRuleEditor() {
        const { ruleId } = state.editingRuleContext;
        const form = dom.ruleEditorForm;
        form.innerHTML = ''; // Очищаем всю форму один раз

        const rule = ruleId ? findElements(Object.values(state.editingRuleContext)).rule : null;
        dom.ruleModalTitle.textContent = ruleId ? 'Настроить правило' : 'Добавить новое правило';

        // --- 1. Создаем HTML для селекта и контейнера параметров ---
        const ruleTypeSelectHtml = `
            <div class="form-group">
                <label for="rule-type-select">Тип правила или группа</label>
                <select id="rule-type-select" name="type_or_group">
                    <option value="">-- Выберите --</option>
                    <optgroup label="Правила">
                        ${state.availableRules.map(r => `<option value="rule:${r.id}" ${rule && rule.type === r.id ? 'selected' : ''}>${r.name}</option>`).join('')}
                    </optgroup>
                    <optgroup label="Группы правил">
                        ${state.availableGroups.map(g => `<option value="group:${g.id}" ${rule && rule.group_id === g.id ? 'selected' : ''}>${g.name}</option>`).join('')}
                    </optgroup>
                </select>
            </div>
            <div id="rule-params-container"></div>
        `;
        form.insertAdjacentHTML('beforeend', ruleTypeSelectHtml);

        // --- 2. Функция для отрисовки только параметров ---
        const renderParams = (selectedValue) => {
            const paramsContainer = form.querySelector('#rule-params-container');
            paramsContainer.innerHTML = ''; // Очищаем только контейнер параметров

            let schema = null;
            if (selectedValue && selectedValue.startsWith('rule:')) {
                const selectedRuleId = selectedValue.split(':')[1];
                const ruleDef = state.availableRules.find(r => r.id === selectedRuleId);
                schema = ruleDef ? ruleDef.params_schema : null;
            }

            if (schema) {
                const currentParams = rule ? rule.params : {};
                schema.forEach(param => {
                    const value = currentParams[param.name] ?? param.default;
                    let fieldHtml = '';

                    if (param.type === 'checkbox') {
                        fieldHtml = `
                            <div class="form-group-checkbox">
                                <input type="checkbox" id="param-${param.name}" name="${param.name}" ${value ? 'checked' : ''}>
                                <label for="param-${param.name}">${param.label}</label>
                            </div>`;
                    } else {
                        fieldHtml = `<div class="form-group">`;
                        fieldHtml += `<label for="param-${param.name}">${param.label}</label>`;
                        if (param.type === 'select') {
                            fieldHtml += `<select id="param-${param.name}" name="${param.name}">`;
                            param.options.forEach(opt => {
                                fieldHtml += `<option value="${opt.value}" ${opt.value === value ? 'selected' : ''}>${opt.label}</option>`;
                            });
                            fieldHtml += `</select>`;
                        } else {
                            fieldHtml += `<input type="text" id="param-${param.name}" name="${param.name}" value="${value || ''}">`;
                        }
                        fieldHtml += `</div>`;
                    }
                    paramsContainer.insertAdjacentHTML('beforeend', fieldHtml);
                });
            }
        };

        // --- 3. Первичный рендер параметров и установка обработчика ---
        const ruleTypeSelect = form.querySelector('#rule-type-select');

        // Сразу отрисовываем параметры для уже существующего правила
        renderParams(ruleTypeSelect.value);

        // Вешаем обработчик для ВСЕХ случаев (новые и существующие правила),
        // чтобы можно было менять тип существующего правила.
        ruleTypeSelect.addEventListener('change', () => {
            renderParams(ruleTypeSelect.value);
        });
    }

    function openRuleModal(context) { // context = { fileId, sheetId, fieldId, ruleId? }
        const { ruleId } = context;
        // For new rules, initialize a 'type' property to be managed during modal interaction
        if (!ruleId) {
            context.type = '';
        } else {
            // For existing rules, get the type from the rule object
            const { rule } = findElements(Object.values(context));
            context.type = rule.type;
        }
        state.editingRuleContext = context;
        state.isRuleModalOpen = true;
        render();
    }

    function closeRuleModal() {
        state.isRuleModalOpen = false;
        state.editingRuleContext = null;
        render();
    }

    async function handleSaveRule(e) {
        e.preventDefault();
        const formData = new FormData(dom.ruleEditorForm);
        const { fileId, sheetId, fieldId, ruleId } = state.editingRuleContext;
        const { field } = findElements([fileId, sheetId, fieldId]);
        const typeOrGroup = formData.get('type_or_group');

        if (!typeOrGroup) {
            showNotification('Необходимо выбрать правило или группу.', 'error');
            return;
        }

        const [itemType, itemId] = typeOrGroup.split(':');

        // Создаем базовый объект для нового или обновляемого правила.
        const baseRule = {
            id: ruleId || newId(),
            order: ruleId
                ? field.rules.find(r => r.id === ruleId)?.order ?? field.rules.length + 1
                : field.rules.length + 1,
            type: null,
            group_id: null,
            params: null
        };

        if (itemType === 'group') {
            baseRule.group_id = itemId;
        } else {
            baseRule.type = itemId;
            const params = {};
            const ruleDef = state.availableRules.find(r => r.id === itemId);
            if (ruleDef && ruleDef.params_schema) {
                ruleDef.params_schema.forEach(p => {
                    if (p.type === 'checkbox') {
                        params[p.name] = formData.get(p.name) === 'on';
                    } else {
                        params[p.name] = formData.get(p.name) || null;
                    }
                });
            }
            if(Object.keys(params).length > 0) {
                baseRule.params = params;
            }
        }

        if (ruleId) {
            const index = field.rules.findIndex(r => r.id === ruleId);
            if (index !== -1) field.rules[index] = baseRule;
        } else {
            field.rules.push(baseRule);
        }

        closeRuleModal();
        await handleSaveProject();
    }

    /**
     * Renders the main statistics block (golden record summary).
     * @param {object} resultsData - The validation results data.
     */
    function renderMainStats(resultsData) {
        const { total_processed_rows, required_field_error_rows_count, validated_at } = resultsData;
        const requiredErrorPercentage = total_processed_rows > 0 ? ((required_field_error_rows_count / total_processed_rows) * 100).toFixed(2) : 0;
        const validationDate = validated_at ? new Date(validated_at).toLocaleString('ru-RU') : 'N/A';

        const statsHtml = `
            <div class="stats-header">
                <div class="stats-summary">
                    <span>Всего обработано строк: <strong>${total_processed_rows}</strong></span>
                    <span id="required-errors-stat" class="${required_field_error_rows_count > 0 ? 'clickable' : ''}" title="Нажмите, чтобы показать/скрыть детали">
                        Строк с ошибками (обязательные поля):
                        <strong>${required_field_error_rows_count}</strong>
                    </span>
                    <span>Процент ошибочных строк: <strong>${requiredErrorPercentage}%</strong></span>
                </div>
                <div class="stats-timestamp">Последняя проверка: ${validationDate}</div>
            </div>
        `;
        dom.goldenRecordStats.innerHTML = statsHtml;
    }

    /**
     * Renders the detailed table for required field errors.
     * @param {Array} required_field_errors - Array of error objects.
     */
    function renderRequiredErrorsDetails(required_field_errors) {
        const detailsHtml = `
            <div class="detailed-results-container required-errors-details">
                <h5>Детализация ошибок в обязательных полях</h5>
                <table class="results-table detailed-table">
                    <thead><tr><th>Файл</th><th>Лист</th><th>Поле</th><th>Строка</th><th>Ошибка</th><th>Значение</th></tr></thead>
                    <tbody>
                        ${required_field_errors.map(err => {
                            const valueCellContent = (err.details && Array.isArray(err.details))
                                ? highlightMisspelledWords(escapeHTML(String(err.value ?? '')), err.details)
                                : escapeHTML(String(err.value ?? ''));
                            return `
                                <tr>
                                    <td>${escapeHTML(err.file_name)}</td>
                                    <td>${escapeHTML(err.sheet_name)}</td>
                                    <td>${escapeHTML(err.field_name)}</td>
                                    <td>${err.row}</td>
                                    <td>${escapeHTML(err.error_type)}</td>
                                    <td class="value-cell">${valueCellContent}</td>
                                </tr>`;
                        }).join('')}
                    </tbody>
                </table>
            </div>`;
        dom.goldenRecordStats.insertAdjacentHTML('beforeend', detailsHtml);
    }

    /**
     * Renders the summary table for a specific sheet, including expandable detailed errors.
     * @param {object} fileResult - The result object for a single file.
     * @param {number} fileIdx - The index of the file.
     */
    function renderSheetSummaries(fileResult, fileIdx) {
        fileResult.sheets.forEach((sheetResult, sheetIdx) => {
            const summaryHtml = `
                <div class="result-sheet-container">
                    <h4>Отчет по листу: ${sheetResult.sheet_name} (Файл: ${fileResult.file_name})</h4>
                    <p class="sheet-stats">Всего строк: ${sheetResult.total_rows}  |  Строк с ошибками: ${sheetResult.sheet_error_rows_count}  |  Процент ошибок: ${sheetResult.sheet_error_percentage}%</p>
                    <table class="results-table summary-table">
                        <thead><tr><th>Тип ошибки</th><th>Количество ошибок</th><th>% от строк листа</th></tr></thead>
                        <tbody>
                            ${sheetResult.rule_summaries.map((summary, ruleIndex) => {
                                const detailsKey = `${fileIdx}-${sheetIdx}-${ruleIndex}`;
                                const isSelected = state.activeRuleDetailsKey === detailsKey;
                                const detailedErrorsHtml = isSelected ? `
                                    <tr class="details-row"><td colspan="3">
                                        <div class="detailed-results-container">
                                            <table class="results-table detailed-table">
                                                <thead><tr><th>Строка</th><th>Поле</th><th>Значение</th></tr></thead>
                                                <tbody>
                                                ${summary.detailed_errors.map(err => {
                                                    const valueCellContent = (err.details && Array.isArray(err.details))
                                                        ? highlightMisspelledWords(escapeHTML(String(err.value ?? '')), err.details)
                                                        : escapeHTML(String(err.value ?? ''));
                                                    return `<tr><td>${err.row}</td><td>${escapeHTML(err.field_name)}</td><td>${valueCellContent}</td></tr>`;
                                                }).join('')}
                                                </tbody>
                                            </table>
                                        </div>
                                    </td></tr>` : '';

                                return `
                                <tr class="summary-row ${summary.error_count > 0 ? 'clickable' : ''} ${isSelected ? 'selected' : ''}"
                                    data-details-key="${detailsKey}"
                                    ${summary.error_count === 0 ? 'style="opacity: 0.6;"' : ''}>
                                    <td>${summary.rule_name}</td>
                                    <td>${summary.error_count}</td>
                                    <td>${summary.error_percentage}%</td>
                                </tr>
                                ${detailedErrorsHtml}
                            `}).join('')}
                        </tbody>
                    </table>
                </div>`;
            dom.summaryResults.innerHTML += summaryHtml;
        });
    }

    /**
     * Main function to render all validation results.
     * It orchestrates calls to more specific render functions.
     */
    function renderValidationResults() {
        const resultsData = state.validationResults;
        dom.resultsContainer.style.display = 'block';
        dom.goldenRecordStats.innerHTML = '';
        dom.summaryResults.innerHTML = '';
        dom.detailedResults.innerHTML = ''; // Clear legacy container, no longer used

        const file_results = resultsData.file_results || resultsData.results;
        if (!resultsData || !file_results) {
            dom.summaryResults.innerHTML = '<div class="success-message">Проверка не выявила данных для анализа.</div>';
            return;
        }

        // 1. Render the main statistics block
        renderMainStats(resultsData);

        // 2. Conditionally render the detailed table for required field errors
        if (state.showRequiredErrorsDetails && resultsData.required_field_error_rows_count > 0) {
            renderRequiredErrorsDetails(resultsData.required_field_errors);
        }

        // 3. Render per-file, per-sheet summaries
        file_results.forEach(renderSheetSummaries);

        // 4. Show a success message if no errors were found at all
        if (resultsData.required_field_error_rows_count === 0 && file_results.every(f => f.sheets.every(s => s.rule_summaries.every(r => r.error_count === 0)))) {
            dom.summaryResults.innerHTML = '<div class="success-message">Проверка успешно завершена. Ошибок не найдено!</div>';
        }
    }

    // --- 6. EVENT HANDLERS & LOGIC ---
    async function handleResultsClick(e) {
        // 2. Handle click on golden record stats
        const requiredStat = e.target.closest('#required-errors-stat.clickable');
        if (requiredStat) {
            state.showRequiredErrorsDetails = !state.showRequiredErrorsDetails;
            renderValidationResults();
            return;
        }

        // 3. Handle click on summary row to see details
        const summaryRow = e.target.closest('.summary-row.clickable');
        if (summaryRow) {
            const detailsKey = summaryRow.dataset.detailsKey;
            state.activeRuleDetailsKey = state.activeRuleDetailsKey === detailsKey ? null : detailsKey;
            state.showRequiredErrorsDetails = false; // Hide other details when showing this one
            renderValidationResults();
            return;
        }
    }

    function findElements(path) {
        const [fileId, sheetId, fieldId, ruleId] = path;
        const file = state.project.files.find(f => f.id === fileId);
        if (!file || !sheetId) return { file };
        const sheet = file.sheets.find(s => s.id === sheetId);
        if (!sheet || !fieldId) return { file, sheet };
        const field = sheet.fields.find(f => f.id === fieldId);
        if (!field || !ruleId) return { file, sheet, field };
        const rule = field.rules.find(r => r.id === ruleId);
        return { file, sheet, field, rule };
    }

    function handleWorkspaceClick(e) {
        const target = e.target;
        const fileCard = target.closest('.file-card');
        const sheetItem = target.closest('.sheet-item');
        const fieldCard = target.closest('.field-card');
        const ruleItem = target.closest('.rule-item');

        const fileId = fileCard ? fileCard.dataset.fileId : null;
        const sheetId = sheetItem ? sheetItem.dataset.sheetId : null;
        const fieldId = fieldCard ? fieldCard.dataset.fieldId : null;
        const ruleId = ruleItem ? ruleItem.dataset.ruleId : null;

        let modified = false;

        if (target.closest('.remove-file-btn')) {
            state.project.files = state.project.files.filter(f => f.id !== fileId);
            modified = true;
        } else if (target.closest('.toggle-sheet-active')) {
            const { sheet } = findElements([fileId, sheetId]);
            if(sheet) { sheet.is_active = !sheet.is_active; modified = true; }
        } else if (target.closest('.configure-sheet-btn')) {
            state.selectedSheetId = state.selectedSheetId === sheetId ? null : sheetId;
            render(); return;
        } else if (target.closest('.toggle-field-required')) {
            const { field } = findElements([fileId, sheetId, fieldId]);
            if(field) { field.is_required = !field.is_required; modified = true; }
        } else if (target.closest('.add-rule-btn')) {
            openRuleModal({ fileId, sheetId, fieldId });
        } else if (target.closest('.edit-rule-btn')) {
            openRuleModal({ fileId, sheetId, fieldId, ruleId });
        } else if (target.closest('.remove-rule-btn')) {
            const { field } = findElements([fileId, sheetId, fieldId]);
            if(field) {
                field.rules = field.rules.filter(r => r.id !== ruleId);
                // Важно! После удаления необходимо пересчитать `order` для всех оставшихся правил,
                // чтобы избежать "дыр" в последовательности, которые могут вызвать ошибку на бэкенде.
                field.rules.forEach((rule, index) => {
                    rule.order = index + 1;
                });
                modified = true;
            }
        } else if (target.closest('.move-rule-up-btn') || target.closest('.move-rule-down-btn')) {
            const { field } = findElements([fileId, sheetId, fieldId, ruleId]);
            if(field) {
                const rules = field.rules;
                const index = rules.findIndex(r => r.id === ruleId);
                const direction = target.closest('.move-rule-up-btn') ? -1 : 1;
                if ((direction === -1 && index > 0) || (direction === 1 && index < rules.length - 1)) {
                    [rules[index], rules[index + direction]] = [rules[index + direction], rules[index]];
                    rules.forEach((r, i) => r.order = i + 1);
                    modified = true;
                }
            }
        }

        if (modified) {
            render();
            handleSaveProject();
        }
    }

    async function handleSaveProject() {
        try {
            const response = await api.saveProject(state.project);
            if (!response.ok) {
                const errorData = await response.json();
                // Throw the actual error data, not just a message.
                // This allows the catch block to inspect the structure.
                throw errorData.detail || errorData;
            }
            showNotification("Проект успешно сохранен!", 'success');
        } catch (error) {
            console.error("Full save error:", error); // Log the full error object for debugging.
            let errorMessage = "Неизвестная ошибка";

            if (typeof error === 'string') {
                errorMessage = error;
            } else if (Array.isArray(error)) {
                // Handle FastAPI validation errors (which are arrays of objects).
                errorMessage = error.map(e => `Поле '${e.loc.join(' → ')}': ${e.msg}`).join('\n');
            } else if (error.message) {
                // Handle standard JS Error objects.
                errorMessage = error.message;
            } else if (typeof error === 'object' && error !== null) {
                // Fallback for other kinds of objects.
                errorMessage = JSON.stringify(error, null, 2);
            }

            // Using textContent, so newline characters will be preserved if the CSS allows.
            showError(`Ошибка сохранения:\n${errorMessage}`);
        }
    }

    async function handleValidate() {
        await handleSaveProject();
        dom.resultsContainer.style.display = 'none';
        dom.progressContainer.style.display = 'block'; // Показываем контейнер прогресса
        state.validationResults = null;
        state.showRequiredErrorsDetails = false;

        try {
            const response = await api.validate();
            if (!response.ok) {
                throw new Error((await response.json()).detail);
            }

            // Получаем начальный статус из ответа API
            const validationResponse = await response.json();

            // Обновляем UI с начальным статусом
            if (validationResponse.initial_status) {
                updateValidationUI(validationResponse.initial_status);
            } else {
                // Если начального статуса нет, используем дефолтный
                updateValidationUI({
                    is_running: true,
                    message: "Запуск проверки...",
                    percentage: 0,
                    processed_rows: 0,
                    total_rows: 0,
                    current_file: "—",
                    current_sheet: "—",
                    current_field: "—",
                    current_rule: "—"
                });
            }

            // Запускаем опрос статуса
            startValidationPolling(projectId);

        } catch (error) {
            showError(`Ошибка валидации: ${error.message}`);
            dom.progressContainer.innerHTML = '<div class="error-container">Не удалось запустить проверку.</div>';
            stopValidationPolling();
        }
    }

    function startValidationPolling(projectId) {
        stopValidationPolling();
        validationPollingId = setInterval(async () => {
            try {
                const response = await fetch(`/api/projects/${projectId}/validation-status`);
                if (!response.ok) {
                    throw new Error(`Failed to get status, server responded with ${response.status}`);
                }
                const status = await response.json();
                updateValidationUI(status);

                if (!status.is_running) {
                    stopValidationPolling();
                    loadAndRenderFinalResults(projectId);
                }
            } catch (error) {
                console.error('Polling error:', error);
                stopValidationPolling();
            }
        }, 500);
    }

    function stopValidationPolling() {
        if (validationPollingId) {
            clearInterval(validationPollingId);
            validationPollingId = null;
        }
    }

    function updateValidationUI(status) {
        // This function is now only responsible for rendering the "in-progress" state.
        // The final state (is_running: false) is handled by the polling function,
        // which stops the interval and calls loadAndRenderFinalResults.
        if (!status) return;

        const percentage = status.percentage ?? (status.total_rows > 0 ? (status.processed_rows / status.total_rows) * 100 : 0);
        const processed = status.processed_rows ?? 0;
        const total = status.total_rows ?? 0;

        const htmlContent = `
            <div style="text-align: center; padding: 2rem;">
                <div class="loading-spinner" style="margin: 0 auto;"></div>
                <p><strong>Выполняется проверка...</strong></p>
                <p>${status.details || status.message || ''}</p>
                <p>Файл: <strong>${status.current_file || '—'}</strong></p>
                <p>Лист: <strong>${status.current_sheet || '—'}</strong></p>
                <p>Поле: <strong>${status.current_field || '—'}</strong></p>
                <p>Правило: <strong>${status.current_rule || '—'}</strong></p>
                <div style="margin-top: 1rem;">
                    <progress id="validation-progress-bar" value="${percentage}" max="100" aria-valuenow="${percentage}" style="width: 100%; height: 10px;"></progress>
                    <div style="display: flex; justify-content: space-between; margin-top: 0.25rem;">
                        <span>${Math.round(processed)} из ${total} строк</span>
                        <span>${percentage.toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        `;
        dom.progressContainer.innerHTML = htmlContent;
    }

    async function loadAndRenderFinalResults(projectId) {
        dom.progressContainer.style.display = 'none'; // Hide progress
        dom.resultsContainer.style.display = 'block'; // Show results container
        try {
            const response = await fetch(`/api/projects/${projectId}/results`);
            if (!response.ok) {
                throw new Error('Не удалось загрузить результаты');
            }
            state.validationResults = await response.json();
            renderValidationResults();
        } catch (error) {
            showError(`Ошибка при загрузке результатов: ${error.message}`);
            dom.resultsContainer.innerHTML = '<div class="error-container">Не удалось загрузить результаты проверки.</div>';
        }
    }

    async function handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        // --- UI Changes for Import ---
        state.showUploadForm = false;
        dom.uploadFormContainer.style.display = 'none'; // Hide immediately
        dom.importProgressContainer.classList.add('indeterminate');
        dom.importProgressContainer.style.display = 'flex';

        try {
            const response = await api.uploadFile(formData);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Неизвестная ошибка сервера');
            }

            // API теперь возвращает только схему файла, а не весь проект
            const newFileSchema = await response.json();

            // Добавляем новый файл в состояние проекта
            state.project.files.push(newFileSchema);

            showNotification(`Файл "${file.name}" успешно импортирован.`, 'success');
            render(); // Перерисовываем весь проект с новым файлом

        } catch(error) {
            showError(`Ошибка импорта файла: ${error.message}`);
            showNotification(`Ошибка импорта файла: ${error.message}`, 'error');
        } finally {
            // --- Reset UI ---
            dom.importProgressContainer.style.display = 'none';
            dom.importProgressContainer.classList.remove('indeterminate');
            dom.fileInput.value = ''; // Сбрасываем input, чтобы можно было загрузить тот же файл снова
        }
    }

    // --- 7. INITIALIZATION ---
    async function init() {
        try {
            const [projectRes, rulesRes, groupsRes, resultsRes] = await Promise.all([
                api.getProject(),
                api.getRules(),
                api.getRuleGroups(),
                api.getResults() // Попытаемся загрузить последние результаты
            ]);

            // Основные данные проекта и правил обязательны
            if (!projectRes.ok) throw new Error((await projectRes.json()).detail);
            if (!rulesRes.ok) throw new Error('Failed to load rules');
            if (!groupsRes.ok) throw new Error('Failed to load rule groups');

            state.project = await projectRes.json();
            state.availableRules = await rulesRes.json();
            state.availableGroups = await groupsRes.json();

            // Результаты проверки не обязательны, обрабатываем их отдельно
            if (resultsRes.ok) {
                state.validationResults = await resultsRes.json();
                renderValidationResults(); // Сразу отображаем, если они есть
            }

            state.isLoading = false;
            render(); // Основной рендер для остальной части страницы
        } catch (error) {
            state.isLoading = false;
            state.error = `Не удалось загрузить проект: ${error.message}`;
            render();
        }
    }

    // Bind event listeners
    dom.saveProjectBtn.addEventListener('click', handleSaveProject);
    dom.validateBtn.addEventListener('click', handleValidate);
    dom.showUploadFormBtn.addEventListener('click', () => { state.showUploadForm = true; render(); });
    dom.cancelUploadBtn.addEventListener('click', () => { state.showUploadForm = false; render(); });
    dom.fileInput.addEventListener('change', handleFileUpload);
    dom.filesListContainer.addEventListener('click', handleWorkspaceClick);
    dom.resultsContainer.addEventListener('click', handleResultsClick);
    dom.resultsContainer.addEventListener('dblclick', async (e) => {
        const misspelledSpan = e.target.closest('.misspelled-word');
        if (!misspelledSpan) return;

        const word = misspelledSpan.textContent.trim();
        if (!word) return;

        if (!confirm(`Добавить слово «${word}» в пользовательский словарь?`)) return;

        try {
            const response = await fetch('/api/dictionary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ word })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Не удалось добавить слово');
            }

            // Убираем подчёркивание у этого слова во всём документе
            document.querySelectorAll(`.misspelled-word`).forEach(span => {
                if (span.textContent.trim().toLowerCase() === word.toLowerCase()) {
                    const textNode = document.createTextNode(span.textContent);
                    span.replaceWith(textNode);
                }
            });

            showNotification(`Слово «${word}» добавлено в словарь.`, 'success');

            // 🔁 Запускаем повторную валидацию проекта, если включена настройка
            if (state.project.auto_revalidate) {
                await handleValidate();
            }

        } catch (err) {
            showError(`Ошибка при добавлении в словарь: ${err.message}`);
        }
    });

    dom.autoRevalidateToggle.addEventListener('change', (e) => {
        if (!state.project) return;
        state.project.auto_revalidate = e.target.checked;
        handleSaveProject(); // Сохраняем изменение настройки
    });

    // Modal listeners
    dom.ruleEditorForm.addEventListener('submit', handleSaveRule);
    dom.closeRuleModalBtn.addEventListener('click', closeRuleModal);
    dom.cancelRuleModalBtn.addEventListener('click', closeRuleModal);

    init();
});