document.addEventListener('DOMContentLoaded', () => {
    const state = {
        groups: [],
        availableRules: [],
        isModalOpen: false,
        editingGroup: null, // or a new group object
    };

    const dom = {
        groupsContainer: document.getElementById('groups-container'),
        showAddGroupBtn: document.getElementById('show-add-group-btn'),
        modal: document.getElementById('group-editor-modal'),
        modalTitle: document.getElementById('group-modal-title'),
        closeModalBtn: document.getElementById('close-group-modal-btn'),
        cancelModalBtn: document.getElementById('cancel-group-modal-btn'),
        groupEditorForm: document.getElementById('group-editor-form'),
    };

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
        if (state.isModalOpen) {
            dom.modal.style.display = 'flex';
            renderModal();
        } else {
            dom.modal.style.display = 'none';
        }
        lucide.createIcons();
    }

    function renderGroups() {
        dom.groupsContainer.innerHTML = '';
        if (state.groups.length === 0) {
            dom.groupsContainer.innerHTML = '<p>Группы правил еще не созданы.</p>';
            return;
        }
        state.groups.forEach(group => {
            const groupCard = document.createElement('div');
            groupCard.className = 'rule-card'; // Re-use existing style
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
        const group = state.editingGroup;
        if (!group) return;

        dom.modalTitle.textContent = group.id ? 'Редактировать группу' : 'Создать новую группу';

        form.innerHTML = `
            <input type="hidden" name="id" value="${group.id || ''}">
            <div class="form-group">
                <label for="group-name">Название группы</label>
                <input type="text" id="group-name" name="name" value="${group.name}" required>
            </div>
            <div class="form-group">
                <label>Логический оператор (условие для ошибки)</label>
                <div class="radio-group">
                    <label><input type="radio" name="logic" value="OR" ${group.logic === 'OR' ? 'checked' : ''}> ИЛИ (любое правило)</label>
                    <label><input type="radio" name="logic" value="AND" ${group.logic === 'AND' ? 'checked' : ''}> И (все правила)</label>
                </div>
            </div>
            <div class="form-group">
                <label>Правила в группе</label>
                <div id="rules-in-group-list"></div>
                <div class="add-rule-container" style="margin-top: 1rem;">
                    <select id="add-rule-select">
                        <option value="">-- Добавить правило --</option>
                        ${state.availableRules.map(r => `<option value="${r.id}">${r.name}</option>`).join('')}
                    </select>
                </div>
            </div>
        `;

        const rulesListContainer = form.querySelector('#rules-in-group-list');
        group.rules.forEach(ruleInGroup => {
            const ruleDef = state.availableRules.find(r => r.id === ruleInGroup.id);
            const ruleItem = document.createElement('div');
            ruleItem.className = 'rule-item';
            ruleItem.dataset.ruleId = ruleInGroup.id;
            ruleItem.innerHTML = `
                <span class="rule-name">${ruleDef.name}</span>
                <div class="rule-actions">
                    <button type="button" class="btn btn-icon danger remove-rule-from-group-btn" title="Удалить из группы"><i data-lucide="trash-2"></i></button>
                </div>
            `;
            rulesListContainer.appendChild(ruleItem);
        });
        lucide.createIcons();

        // Event listener for adding a rule
        form.querySelector('#add-rule-select').addEventListener('change', (e) => {
            const ruleId = e.target.value;
            if (!ruleId) return;
            // Avoid duplicates
            if (!state.editingGroup.rules.some(r => r.id === ruleId)) {
                state.editingGroup.rules.push({ id: ruleId, params: null });
                renderModal(); // Re-render modal to show new rule
            }
            e.target.value = ''; // Reset select
        });

        // Event listener for removing a rule
        rulesListContainer.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.remove-rule-from-group-btn');
            if(removeBtn) {
                const ruleId = removeBtn.closest('.rule-item').dataset.ruleId;
                state.editingGroup.rules = state.editingGroup.rules.filter(r => r.id !== ruleId);
                renderModal();
            }
        });
    }

    async function handleSaveGroup(e) {
        e.preventDefault();
        const formData = new FormData(dom.groupEditorForm);
        const name = formData.get('name');
        const logic = formData.get('logic');

        if (!name) {
            showNotification('Название группы не может быть пустым.', 'error');
            return;
        }

        const groupData = {
            id: state.editingGroup.id,
            name,
            logic,
            rules: state.editingGroup.rules,
        };

        try {
            let updatedGroup;
            if (groupData.id) {
                const res = await api.updateGroup(groupData.id, groupData);
                if (!res.ok) throw new Error(await res.text());
                updatedGroup = await res.json();
                const index = state.groups.findIndex(g => g.id === updatedGroup.id);
                state.groups[index] = updatedGroup;
            } else {
                const res = await api.createGroup(groupData);
                if (!res.ok) throw new Error(await res.text());
                updatedGroup = await res.json();
                state.groups.push(updatedGroup);
            }
            state.isModalOpen = false;
            render();
        } catch (error) {
            console.error("Ошибка сохранения группы:", error);
            showNotification("Не удалось сохранить группу.", 'error');
        }
    }

    async function init() {
        try {
            const [groupsRes, rulesRes] = await Promise.all([api.getGroups(), api.getRules()]);
            if (!groupsRes.ok || !rulesRes.ok) {
                throw new Error('Не удалось загрузить данные.');
            }
            state.groups = await groupsRes.json();
            state.availableRules = await rulesRes.json();
            render();
        } catch (error) {
            console.error("Ошибка инициализации:", error);
            dom.groupsContainer.innerHTML = `<p class="error">${error.message}</p>`;
        }
    }

    // Event Listeners
    dom.showAddGroupBtn.addEventListener('click', () => {
        state.editingGroup = { name: '', logic: 'OR', rules: [] };
        state.isModalOpen = true;
        render();
    });

    dom.closeModalBtn.addEventListener('click', () => {
        state.isModalOpen = false;
        render();
    });

    dom.cancelModalBtn.addEventListener('click', () => {
        state.isModalOpen = false;
        render();
    });

    dom.groupEditorForm.addEventListener('submit', handleSaveGroup);

    dom.groupsContainer.addEventListener('click', async (e) => {
        const editBtn = e.target.closest('.edit-group-btn');
        const deleteBtn = e.target.closest('.delete-group-btn');

        if (editBtn) {
            const groupId = editBtn.closest('.rule-card').dataset.id;
            const group = state.groups.find(g => g.id === groupId);
            state.editingGroup = JSON.parse(JSON.stringify(group)); // Deep copy
            state.isModalOpen = true;
            render();
        }

        if (deleteBtn) {
            const groupId = deleteBtn.closest('.rule-card').dataset.id;
            if (confirm('Вы уверены, что хотите удалить эту группу?')) {
                try {
                    const res = await api.deleteGroup(groupId);
                    if (!res.ok) throw new Error('Failed to delete');
                    state.groups = state.groups.filter(g => g.id !== groupId);
                    render();
                } catch (error) {
                    showNotification('Не удалось удалить группу.', 'error');
                }
            }
        }
    });

    init();
});