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
                    <button class="btn btn-icon danger remove-field-btn" title="Удалить поле"><i data-lucide="trash-2"></i></button>
                </div>
            </div>
            <div class="rules-list"></div>
            <div class="add-rule-form">
                <select class="add-rule-type"><option value="">-- Выбрать правило --</option>${state.availableRules.map(r => `<option value="${r.id}">${r.name}</option>`).join('')}</select>
                <input type="text" class="add-rule-value" placeholder="Параметр (если нужно)">
                <button class="btn btn-primary add-rule-btn" title="Добавить правило"><i data-lucide="plus"></i></button>
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
        const ruleDef = state.availableRules.find(r => r.id === rule.type);
        const ruleName = ruleDef ? ruleDef.name : rule.type;
        const ruleValue = rule.value ? `: ${rule.value}` : '';

        ruleItem.innerHTML = `
            <span class="rule-name">${ruleName}${ruleValue}</span>
            <div class="rule-actions">
                <button class="btn btn-icon move-rule-up-btn" title="Переместить вверх"><i data-lucide="arrow-up"></i></button>
                <button class="btn btn-icon move-rule-down-btn" title="Переместить вниз"><i data-lucide="arrow-down"></i></button>
                <button class="btn btn-icon danger remove-rule-btn" title="Удалить правило"><i data-lucide="trash-2"></i></button>
            </div>`;
        return ruleItem;
    }

    function renderValidationResults(results) {
        dom.resultsContainer.style.display = 'block';
        dom.goldenRecordStats.innerHTML = `<div class="stats-summary"><span>Всего строк: <strong>${results.total_rows}</strong></span><span>Строк с ошибками: <strong>${results.error_rows_count}</strong></span></div>`;
        if (results.errors.length === 0) {
            dom.summaryResults.innerHTML = '<div class="success-message">Проверка успешно завершена. Ошибок не найдено!</div>';
            dom.detailedResults.innerHTML = '';
            return;
        }
        const errorsByRule = results.errors.reduce((acc, error) => {
            if (!acc[error.rule_name]) acc[error.rule_name] = [];
            acc[error.rule_name].push(error);
            return acc;
        }, {});
        dom.summaryResults.innerHTML = `<table class="results-table summary-table"><thead><tr><th>Правило</th><th>Количество ошибок</th></tr></thead><tbody>${Object.entries(errorsByRule).map(([name, errs]) => `<tr class="summary-row" data-rule-name="${name}"><td>${name}</td><td>${errs.length}</td></tr>`).join('')}</tbody></table>`;
        dom.detailedResults.innerHTML = '';
    }

    // --- 6. EVENT HANDLERS & LOGIC ---
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
            // This is a UI-only change, so render and return immediately.
            render();
            return;
        } else if (target.closest('.remove-field-btn')) {
            const { sheet } = findElements([fileId, sheetId, fieldId]);
            if(sheet) { sheet.fields = sheet.fields.filter(f => f.id !== fieldId); modified = true; }
        } else if (target.closest('.toggle-field-required')) {
            const { field } = findElements([fileId, sheetId, fieldId]);
            if(field) { field.is_required = !field.is_required; modified = true; }
        } else if (target.closest('.add-rule-btn')) {
            const form = target.closest('.add-rule-form');
            const type = form.querySelector('.add-rule-type').value;
            const value = form.querySelector('.add-rule-value').value.trim();
            if (type) {
                const { field } = findElements([fileId, sheetId, fieldId]);
                if(field) {
                    field.rules.push({ id: newId(), type, value: value || null, order: field.rules.length + 1 });
                    // Reset the form for better UX
                    form.querySelector('.add-rule-type').value = "";
                    form.querySelector('.add-rule-value').value = "";
                    modified = true;
                }
            }
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

        render();
        if (modified) handleSaveProject();
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
        await handleSaveProject();
        dom.resultsContainer.style.display = 'block';
        try {
            const response = await api.validate();
            if (!response.ok) throw new Error((await response.json()).detail);
            const results = await response.json();
            renderValidationResults(results);
        } catch (error) {
            showError(`Ошибка валидации: ${error.message}`);
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

    init();
});