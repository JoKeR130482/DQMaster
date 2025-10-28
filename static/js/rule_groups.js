document.addEventListener('DOMContentLoaded', () => {
    const state = {
        groups: [],
        availableRules: [],
        isModalOpen: false,
        editingGroup: null,
        isParamsModalOpen: false,
        editingRule: null,
    };

    const dom = {
        groupsContainer: document.getElementById('groups-container'),
        showAddGroupBtn: document.getElementById('show-add-group-btn'),
        modal: document.getElementById('group-editor-modal'),
        modalTitle: document.getElementById('group-modal-title'),
        closeModalBtn: document.getElementById('close-group-modal-btn'),
        cancelModalBtn: document.getElementById('cancel-group-modal-btn'),
        groupEditorForm: document.getElementById('group-editor-form'),
        paramsModal: document.getElementById('rule-params-modal'),
        paramsModalTitle: document.getElementById('rule-params-modal-title'),
        closeParamsModalBtn: document.getElementById('close-rule-params-modal-btn'),
        cancelParamsModalBtn: document.getElementById('cancel-rule-params-modal-btn'),
        paramsForm: document.getElementById('rule-params-form'),
    };

    // ... (api object is unchanged) ...
    const api = {
        getGroups: () => fetch('/api/rule-groups'),
        getRules: () => fetch('/api/rules'),
        createGroup: (group) => fetch('/api/rule-groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(group),
        }),
        updateGroup: (id, group) => fetch(`/api/rule-groups/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(group),
        }),
        deleteGroup: (id) => fetch(`/api/rule-groups/${id}`, { method: 'DELETE' }),
    };


    function render() {
        renderGroups();
        dom.modal.style.display = state.isModalOpen ? 'flex' : 'none';
        dom.paramsModal.style.display = state.isParamsModalOpen ? 'flex' : 'none';

        if (state.isModalOpen && !state.isParamsModalOpen) renderModal();
        if (state.isParamsModalOpen) renderParamsModal();

        lucide.createIcons();
    }

    // ... (renderGroups is unchanged) ...
    function renderGroups() {
        dom.groupsContainer.innerHTML = '';
        if (state.groups.length === 0) {
            dom.groupsContainer.innerHTML = '<p>Группы правил еще не созданы.</p>';
            return;
        }
        state.groups.forEach(group => {
            const groupCard = document.createElement('div');
            groupCard.className = 'rule-card';
            groupCard.dataset.id = group.id;
            groupCard.innerHTML = `
                <div class="card-header">
                    <h3 class="card-title">${group.name}</h3>
                    <div class="card-actions">
                        <button class="btn btn-icon edit-group-btn" title="Редактировать"><i data-lucide="edit"></i></button>
                        <button class="btn btn-icon danger delete-group-btn" title="Удалить"><i data-lucide="trash-2"></i></button>
                    </div>
                </div>
                <div class="rule-description">
                    Логика: <strong>${group.logic}</strong>. Правил в группе: <strong>${group.rules.length}</strong>.
                </div>
                <div class="card-id">ID: ${group.id}</div>
            `;
            dom.groupsContainer.appendChild(groupCard);
        });
    }

    function renderModal() {
        const form = dom.groupEditorForm;
        const modalBody = form.querySelector('.modal-body');
        const group = state.editingGroup;
        if (!group) return;

        dom.modalTitle.textContent = group.id ? 'Редактировать группу' : 'Создать новую группу';

        if (!modalBody.querySelector('#group-name')) {
            modalBody.innerHTML = `
                <input type="hidden" name="id" value="${group.id || ''}">
                <div class="form-group">
                    <label for="group-name">Название группы *</label>
                    <input type="text" id="group-name" name="name" required placeholder="Например: Некорректное название продукта">
                </div>
                <div class="form-group">
                    <label>Логический оператор (условие для ошибки)</label>
                    <div class="radio-group">
                        <label><input type="radio" name="logic" value="OR"><strong>ИЛИ</strong> — ошибка, если хотя бы одно правило нарушено</label>
                        <label><input type="radio" name="logic" value="AND"><strong>И</strong> — ошибка, если все правила нарушены</label>
                    </div>
                </div>
                <div class="form-group">
                    <label for="add-rule-select">Добавить правило в группу</label>
                    <select id="add-rule-select">
                        <option value="">-- Добавить правило --</option>
                        ${state.availableRules.map(r => `<option value="${r.id}">${r.name}</option>`).join('')}
                    </select>
                    <div class="rules-in-group-list" id="rules-in-group-list"></div>
                </div>
            `;
        }

        modalBody.querySelector('#group-name').value = group.name || '';
        modalBody.querySelector(`input[name="logic"][value="${group.logic || 'OR'}"]`).checked = true;

        renderRulesInGroup();
    }

    // ... (renderRulesInGroup is unchanged) ...
    function renderRulesInGroup() {
        const rulesListContainer = dom.groupEditorForm.querySelector('#rules-in-group-list');
        rulesListContainer.innerHTML = '';
        state.editingGroup.rules.forEach(ruleInGroup => {
            const ruleDef = state.availableRules.find(r => r.id === ruleInGroup.id);
            if (!ruleDef) return;

            const ruleItem = document.createElement('div');
            ruleItem.className = 'rule-item';
            ruleItem.dataset.ruleId = ruleInGroup.id;

            let configureBtn = '';
            if (ruleDef.is_configurable) {
                configureBtn = `<button type="button" class="btn btn-icon configure-rule-btn" title="Настроить параметры"><i data-lucide="settings-2"></i></button>`;
            }

            ruleItem.innerHTML = `
                <span class="rule-name">${ruleDef.name}</span>
                <div class="rule-actions">
                    ${configureBtn}
                    <button type="button" class="btn btn-icon danger remove-rule-from-group-btn" title="Удалить из группы"><i data-lucide="trash-2"></i></button>
                </div>
            `;
            rulesListContainer.appendChild(ruleItem);
        });
        lucide.createIcons();
    }


    function renderParamsModal() {
        const { ruleId } = state.editingRule;
        const ruleDef = state.availableRules.find(r => r.id === ruleId);
        const ruleInGroup = state.editingGroup.rules.find(r => r.id === ruleId);
        if (!ruleDef || !ruleInGroup) return;

        dom.paramsModalTitle.textContent = `Настроить: ${ruleDef.name}`;
        const modalBody = dom.paramsForm.querySelector('.modal-body');
        modalBody.innerHTML = '';

        if (!ruleDef.params_schema) {
            modalBody.innerHTML = '<p>У этого правила нет настраиваемых параметров.</p>';
            return;
        }

        const currentParams = ruleInGroup.params || {};
        ruleDef.params_schema.forEach(param => {
            const value = currentParams[param.name] ?? param.default;
            let fieldHtml = '';
            if (param.type === 'checkbox') {
                fieldHtml = `<div class="form-group-checkbox"><input type="checkbox" id="param-${param.name}" name="${param.name}" ${value ? 'checked' : ''}><label for="param-${param.name}">${param.label}</label></div>`;
            } else {
                fieldHtml = `<div class="form-group"><label for="param-${param.name}">${param.label}</label>`;
                if (param.type === 'select') {
                    fieldHtml += `<select id="param-${param.name}" name="${param.name}">${param.options.map(opt => `<option value="${opt.value}" ${opt.value === value ? 'selected' : ''}>${opt.label}</option>`).join('')}</select>`;
                } else {
                    fieldHtml += `<input type="text" id="param-${param.name}" name="${param.name}" value="${value || ''}">`;
                }
                fieldHtml += `</div>`;
            }
            modalBody.insertAdjacentHTML('beforeend', fieldHtml);
        });
    }

    function openParamsModal(ruleId) {
        state.editingRule = { ruleId };
        state.isModalOpen = false; // Hide main modal
        state.isParamsModalOpen = true;
        render();
    }

    function closeParamsModal() {
        state.isParamsModalOpen = false;
        state.editingRule = null;
        state.isModalOpen = true; // Show main modal again
        render();
    }

    // ... (the rest of the functions are mostly the same, just adjusted to use the new flow) ...
    async function handleAddRuleToGroup(e) {
        const ruleId = e.target.value;
        if (!ruleId) return;
        e.target.value = '';

        if (state.editingGroup.rules.some(r => r.id === ruleId)) return;

        const ruleDef = state.availableRules.find(r => r.id === ruleId);
        if (!ruleDef) return;

        state.editingGroup.rules.push({ id: ruleId, params: null });

        if (ruleDef.is_configurable) {
            openParamsModal(ruleId);
        } else {
            renderRulesInGroup();
        }
    }

    const generateId = () => `grp_${Date.now().toString(36)}_${Math.random().toString(36).substr(2, 9)}`;

    async function handleSaveGroup(e) {
        e.preventDefault();
        state.editingGroup.name = dom.groupEditorForm.querySelector('#group-name').value;
        state.editingGroup.logic = dom.groupEditorForm.querySelector('input[name="logic"]:checked').value;

        if (!state.editingGroup.name) {
            alert('Название группы не может быть пустым.');
            return;
        }

        const groupData = { ...state.editingGroup, id: state.editingGroup.id || generateId() };

        try {
            const res = groupData.id && state.groups.some(g => g.id === groupData.id)
                ? await api.updateGroup(groupData.id, groupData)
                : await api.createGroup(groupData);

            if (!res.ok) throw new Error(await res.text());

            await init(); // Re-fetch all data to ensure consistency
            state.isModalOpen = false;
            render();
        } catch (error) {
            console.error("Ошибка сохранения группы:", error);
        }
    }

    async function handleSaveParams(e) {
        e.preventDefault();
        const formData = new FormData(dom.paramsForm);
        const { ruleId } = state.editingRule;
        const ruleInGroup = state.editingGroup.rules.find(r => r.id === ruleId);
        const ruleDef = state.availableRules.find(r => r.id === ruleId);

        if (ruleInGroup && ruleDef && ruleDef.params_schema) {
            const params = {};
            ruleDef.params_schema.forEach(p => {
                if (p.type === 'checkbox') {
                    params[p.name] = formData.has(p.name);
                } else {
                    params[p.name] = formData.get(p.name) || null;
                }
            });
            ruleInGroup.params = params;
        }

        closeParamsModal();
    }

    async function init() {
        try {
            const [groupsRes, rulesRes] = await Promise.all([api.getGroups(), api.getRules()]);
            if (!groupsRes.ok || !rulesRes.ok) throw new Error('Не удалось загрузить данные.');

            state.groups = await groupsRes.json();
            state.availableRules = await rulesRes.json();
            render();
        } catch (error) {
            console.error("Ошибка инициализации:", error);
        }
    }

    // Event Listeners
    dom.showAddGroupBtn.addEventListener('click', () => {
        state.editingGroup = { name: '', logic: 'OR', rules: [] };
        state.isModalOpen = true;
        render();
    });

    dom.closeModalBtn.addEventListener('click', () => { state.isModalOpen = false; render(); });
    dom.cancelModalBtn.addEventListener('click', () => { state.isModalOpen = false; render(); });
    dom.groupEditorForm.addEventListener('submit', handleSaveGroup);

    dom.groupEditorForm.addEventListener('change', e => {
        if (e.target.id === 'add-rule-select') handleAddRuleToGroup(e);
    });

    dom.groupEditorForm.addEventListener('click', e => {
        const removeBtn = e.target.closest('.remove-rule-from-group-btn');
        if (removeBtn) {
            const ruleId = removeBtn.closest('.rule-item').dataset.ruleId;
            state.editingGroup.rules = state.editingGroup.rules.filter(r => r.id !== ruleId);
            renderRulesInGroup();
        }

        const configureBtn = e.target.closest('.configure-rule-btn');
        if(configureBtn) {
            const ruleId = configureBtn.closest('.rule-item').dataset.ruleId;
            openParamsModal(ruleId);
        }
    });

    dom.closeParamsModalBtn.addEventListener('click', closeParamsModal);
    dom.cancelParamsModalBtn.addEventListener('click', closeParamsModal);
    dom.paramsForm.addEventListener('submit', handleSaveParams);

    dom.groupsContainer.addEventListener('click', async (e) => {
        const editBtn = e.target.closest('.edit-group-btn');
        if (editBtn) {
            const groupId = editBtn.closest('.rule-card').dataset.id;
            const group = state.groups.find(g => g.id === groupId);
            state.editingGroup = JSON.parse(JSON.stringify(group)); // Deep copy
            state.isModalOpen = true;
            render();
        }

        const deleteBtn = e.target.closest('.delete-group-btn');
        if (deleteBtn) {
            const groupId = deleteBtn.closest('.rule-card').dataset.id;
            if (confirm('Вы уверены, что хотите удалить эту группу?')) {
                try {
                    await api.deleteGroup(groupId);
                    await init();
                } catch (error) {
                    console.error('Не удалось удалить группу.', error);
                }
            }
        }
    });

    init();
});