document.addEventListener('DOMContentLoaded', () => {
    // --- 1. STATE & CONSTANTS ---
    const projectId = window.location.pathname.split('/').pop();
    let state = {
        project: null,
        availableRules: [],
        isLoading: true,
        error: null,
        showUploadForm: false,
        selectedSheetId: null,
        validationResults: null,
        isRuleModalOpen: false,
        editingRuleContext: null, // { fileId, sheetId, fieldId, ruleId? }
        showRequiredErrorsDetails: false,
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
        filesListContainer: document.getElementById('files-list-container'),
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
    };

    // --- 3. API HELPERS ---
    const api = {
        getProject: () => fetch(`/api/projects/${projectId}`),
        getRules: () => fetch('/api/rules'),
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
    const newId = () => `id_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

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

        dom.projectNameHeader.textContent = state.project.name;
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
            fileCard.innerHTML = `
                <div class="file-header">
                    <h3 class="file-name">${file.name}</h3>
                    <div class="file-actions">
                    <button class="btn btn-icon danger remove-file-btn" title="Удалить файл"><i data-lucide="trash-2"></i></button>
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
        const { ruleId, type: selectedRuleType } = state.editingRuleContext;
        const form = dom.ruleEditorForm;
        form.innerHTML = '';

        const rule = ruleId ? findElements(Object.values(state.editingRuleContext)).rule : null;
        dom.ruleModalTitle.textContent = ruleId ? 'Настроить правило' : 'Добавить новое правило';

        let schema = null;

        const ruleTypeSelectHtml = `
            <div class="form-group">
                <label for="rule-type-select">Тип правила</label>
                <select id="rule-type-select" name="type" ${rule ? 'disabled' : ''}>
                    <option value="">-- Выберите правило --</option>
                    ${state.availableRules.map(r => `<option value="${r.id}" ${r.id === selectedRuleType ? 'selected' : ''}>${r.name}</option>`).join('')}
                </select>
            </div>
        `;
        form.insertAdjacentHTML('beforeend', ruleTypeSelectHtml);

        if (selectedRuleType) {
            const ruleDef = state.availableRules.find(r => r.id === selectedRuleType);
            schema = ruleDef ? ruleDef.params_schema : null;
        }

        if (schema) {
            const currentParams = rule ? rule.params : {};
            schema.forEach(param => {
                const value = currentParams[param.name] ?? param.default;
                let fieldHtml = '';

                if (param.type === 'checkbox') {
                    // Use the dedicated checkbox group class for proper styling
                    fieldHtml = `
                        <div class="form-group-checkbox">
                            <input type="checkbox" id="param-${param.name}" name="${param.name}" ${value ? 'checked' : ''}>
                            <label for="param-${param.name}">${param.label}</label>
                        </div>`;
                } else {
                    // Standard form group for other types
                    fieldHtml = `<div class="form-group">`;
                    fieldHtml += `<label for="param-${param.name}">${param.label}</label>`;
                    if (param.type === 'select') {
                        fieldHtml += `<select id="param-${param.name}" name="${param.name}">`;
                        param.options.forEach(opt => {
                            fieldHtml += `<option value="${opt.value}" ${opt.value === value ? 'selected' : ''}>${opt.label}</option>`;
                        });
                        fieldHtml += `</select>`;
                    } else { // text
                        fieldHtml += `<input type="text" id="param-${param.name}" name="${param.name}" value="${value || ''}">`;
                    }
                    fieldHtml += `</div>`;
                }
                form.insertAdjacentHTML('beforeend', fieldHtml);
            });
        }

        const ruleTypeSelect = form.querySelector('#rule-type-select');
        if (!rule) { // Only allow changing type for new rules
            ruleTypeSelect.addEventListener('change', () => {
                state.editingRuleContext.type = ruleTypeSelect.value;
                renderRuleEditor(); // Re-render modal with new schema
            });
        }
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

        const type = formData.get('type');
        if (!type) {
            showNotification('Необходимо выбрать тип правила.', 'error');
            return;
        }

        const ruleDef = state.availableRules.find(r => r.id === type);
        const params = {};
        if (ruleDef && ruleDef.params_schema) {
            ruleDef.params_schema.forEach(p => {
                if (p.type === 'checkbox') {
                    params[p.name] = formData.has(p.name);
                } else {
                    params[p.name] = formData.get(p.name);
                }
            });
        }

        if (ruleId) { // Editing existing rule
            const rule = field.rules.find(r => r.id === ruleId);
            rule.params = params;
        } else { // Adding new rule
            field.rules.push({
                id: newId(),
                type: type,
                params: params,
                value: null, // Deprecate 'value'
                order: field.rules.length + 1
            });
        }
        closeRuleModal();
        await handleSaveProject();
        render(); // Re-render main UI
    }

    function renderValidationResults() {
        const resultsData = state.validationResults;
        dom.resultsContainer.style.display = 'block';
        dom.goldenRecordStats.innerHTML = ''; // Clear old stats
        dom.summaryResults.innerHTML = '';
        dom.detailedResults.innerHTML = '';

        if (!resultsData || !resultsData.results || resultsData.results.length === 0) {
            dom.summaryResults.innerHTML = '<div class="success-message">Проверка не выявила данных для анализа.</div>';
            return;
        }

        const allSheets = resultsData.results.flatMap(f => f.sheets);
        if (allSheets.length === 0) {
            dom.summaryResults.innerHTML = '<div class="success-message">Проверка не выявила данных для анализа.</div>';
            return;
        }

        const overallTotalRows = allSheets.reduce((sum, s) => sum + s.total_rows, 0);
        const overallRequiredErrorRows = allSheets.reduce((sum, s) => sum + s.required_field_error_rows_count, 0);
        const requiredErrorPercentage = overallTotalRows > 0 ? ((overallRequiredErrorRows / overallTotalRows) * 100).toFixed(2) : 0;

        if (overallTotalRows === 0) {
             dom.summaryResults.innerHTML = '<div class="success-message">Проверка успешно завершена. Файлы пусты.</div>';
             dom.goldenRecordStats.innerHTML = '';
             return;
        }

        // New stats block
        const statsHtml = `
            <div class="stats-summary">
                <span>Всего строк: <strong>${overallTotalRows}</strong></span>
                <span id="required-errors-stat" class="${overallRequiredErrorRows > 0 ? 'clickable' : ''}" title="Нажмите, чтобы показать/скрыть детали">
                    Ошибочных строк (обязательные поля):
                    <strong>${overallRequiredErrorRows}</strong>
                </span>
                <span>Процент ошибочных строк: <strong>${requiredErrorPercentage}%</strong></span>
            </div>
        `;
        dom.goldenRecordStats.innerHTML = statsHtml;

        // Conditionally render the detailed required errors
        if (state.showRequiredErrorsDetails && overallRequiredErrorRows > 0) {
            const allRequiredErrors = allSheets.flatMap(s => s.required_field_errors);
            const detailsHtml = `
                <div class="detailed-results-container required-errors-details">
                    <h5>Детализация ошибок в обязательных полях</h5>
                    <table class="results-table detailed-table">
                        <thead>
                            <tr>
                                <th>Строка</th>
                                <th>Поле</th>
                                <th>Значение</th>
                                <th>Ошибка</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${allRequiredErrors.map(err => `
                                <tr>
                                    <td>${err.row}</td>
                                    <td>${err.column}</td>
                                    <td>${err.value}</td>
                                    <td>${err.error}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>`;
            dom.goldenRecordStats.insertAdjacentHTML('beforeend', detailsHtml);
        }

        // Render the secondary report (per-rule errors)
        resultsData.results.forEach((fileResult, fileIdx) => {
            fileResult.sheets.forEach((sheetResult, sheetIdx) => {
                if (sheetResult.rule_summaries.length > 0) {
                    const summaryHtml = `
                        <div class="result-sheet-container">
                            <h4>Отчет по правилам: ${sheetResult.sheet_name} (Файл: ${fileResult.file_name})</h4>
                            <table class="results-table summary-table">
                                <thead>
                                    <tr>
                                        <th>Правило</th>
                                        <th>Кол-во ошибок</th>
                                        <th>% от строк листа</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${sheetResult.rule_summaries.map((summary, ruleIndex) => `
                                        <tr class="summary-row ${summary.error_count > 0 ? 'clickable' : ''}"
                                            data-file-idx="${fileIdx}"
                                            data-sheet-idx="${sheetIdx}"
                                            data-rule-idx="${ruleIndex}"
                                            ${summary.error_count === 0 ? 'style="color: #888;"' : ''}>
                                            <td>${summary.rule_name}</td>
                                            <td>${summary.error_count}</td>
                                            <td>${summary.error_percentage}%</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                    dom.summaryResults.innerHTML += summaryHtml;
                }
            });
        });

        if (dom.summaryResults.innerHTML.trim() === '' && overallRequiredErrorRows === 0) {
            dom.summaryResults.innerHTML = '<div class="success-message">Проверка успешно завершена. Ошибок не найдено!</div>';
        }
    }

    // --- 6. EVENT HANDLERS & LOGIC ---
    function handleResultsClick(e) {
        // Handle clicks on the main stats
        const stat = e.target.closest('#required-errors-stat');
        if (stat) {
            state.showRequiredErrorsDetails = !state.showRequiredErrorsDetails;
            renderValidationResults(); // Re-render to show/hide details
            return;
        }

        // Handle clicks on the rule summary rows
        const row = e.target.closest('.summary-row.clickable');
        if (!row) return;

        const isActive = row.classList.contains('selected');

        // Deselect all rows and clear details
        document.querySelectorAll('.summary-row.selected').forEach(r => r.classList.remove('selected'));
        dom.detailedResults.innerHTML = '';

        if (isActive) {
            return;
        }

        row.classList.add('selected');

        const { fileIdx, sheetIdx, ruleIdx } = row.dataset;
        const ruleSummary = state.validationResults.results[fileIdx].sheets[sheetIdx].rule_summaries[ruleIdx];

        if (!ruleSummary || ruleSummary.error_count === 0) return;

        const detailsHtml = `
            <div class="detailed-results-container">
                <h5>Детализация ошибок для правила: "${ruleSummary.rule_name}"</h5>
                <table class="results-table detailed-table">
                    <thead>
                        <tr>
                            <th>Строка</th>
                            <th>Колонка</th>
                            <th>Значение с ошибкой</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${ruleSummary.detailed_errors.map(err => `
                            <tr>
                                <td>${err.row}</td>
                                <td>${err.column}</td>
                                <td>${err.value}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        dom.detailedResults.innerHTML = detailsHtml;
        dom.detailedResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
            const { field } = findElements([fileId, sheetId, fieldId, ruleId]);
            if(field) { field.rules = field.rules.filter(r => r.id !== ruleId); modified = true; }
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
            if (!response.ok) throw new Error((await response.json()).detail);
            showNotification("Проект успешно сохранен!", 'success');
        } catch (error) {
            showError(`Ошибка сохранения: ${error.message}`);
        }
    }

    async function handleValidate() {
        await handleSaveProject(); // Ensure latest config is saved before validation
        dom.resultsContainer.style.display = 'block';
        dom.summaryResults.innerHTML = '<div class="loading-spinner"></div>'; // Show loading indicator
        dom.detailedResults.innerHTML = '';
        state.validationResults = null;

        try {
            const response = await api.validate();
            if (!response.ok) throw new Error((await response.json()).detail);
            state.validationResults = await response.json();
            renderValidationResults();
        } catch (error) {
            showError(`Ошибка валидации: ${error.message}`);
            dom.summaryResults.innerHTML = ''; // Clear loading indicator on error
        }
    }

    async function handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);
        dom.loading.style.display = 'block';
        try {
            const response = await api.uploadFile(formData);
            if (!response.ok) throw new Error((await response.json()).detail);
            state.project = await response.json();
            state.showUploadForm = false;
            render();
        } catch(error) {
            showError(`Ошибка загрузки файла: ${error.message}`);
        } finally {
            dom.loading.style.display = 'none';
        }
    }

    // --- 7. INITIALIZATION ---
    async function init() {
        try {
            const [projectRes, rulesRes] = await Promise.all([api.getProject(), api.getRules()]);
            if (!projectRes.ok) throw new Error((await projectRes.json()).detail);
            if (!rulesRes.ok) throw new Error('Failed to load rules');

            state.project = await projectRes.json();
            state.availableRules = await rulesRes.json();
            state.isLoading = false;
            render();
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
    // Modal listeners
    dom.ruleEditorForm.addEventListener('submit', handleSaveRule);
    dom.closeRuleModalBtn.addEventListener('click', closeRuleModal);
    dom.cancelRuleModalBtn.addEventListener('click', closeRuleModal);

    init();
});