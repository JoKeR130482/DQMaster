document.addEventListener('DOMContentLoaded', () => {

    // --- 1. STATE MANAGEMENT ---
    const state = {
        projects: [],
        isLoading: true,
        viewMode: 'grid', // 'grid' or 'table'
        searchTerm: '',
        sortConfig: { key: 'name', direction: 'asc' },
        editingId: null,
        showAddForm: false,
    };

    // --- 2. DOM ELEMENTS ---
    const dom = {
        loadingSpinner: document.getElementById('loading'),
        errorContainer: document.getElementById('error-container'),
        projectsContainer: document.getElementById('projects-container'),
        searchInput: document.getElementById('search-input'),
        viewGridBtn: document.getElementById('view-grid-btn'),
        viewTableBtn: document.getElementById('view-table-btn'),
        showAddFormBtn: document.getElementById('show-add-form-btn'),
        addProjectFormContainer: document.getElementById('add-project-form-container'),
        addNameInput: document.getElementById('add-name'),
        addDescriptionInput: document.getElementById('add-description'),
        addProjectBtn: document.getElementById('add-project-btn'),
        cancelAddProjectBtn: document.getElementById('cancel-add-project-btn'),
        emptyState: document.getElementById('empty-state'),
        notificationToast: document.getElementById('notification-toast'),
    };

    // --- 3. API HELPERS ---
    const api = {
        getProjects: () => fetch('/api/projects'),
        createProject: (data) => fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        }),
        updateProjectPartial: (id, data) => fetch(`/api/projects/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        }),
        deleteProject: (id) => fetch(`/api/projects/${id}`, { method: 'DELETE' }),
    };

    // --- 4. UTILS ---
    const formatDate = (dateString) => new Date(dateString).toLocaleDateString('ru-RU');
    const escapeHTML = (str) => {
        if (typeof str !== 'string') return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }
    const showNotification = (message, type = 'success') => {
        dom.notificationToast.textContent = message;
        dom.notificationToast.className = `toast ${type} show`;
        setTimeout(() => { dom.notificationToast.className = dom.notificationToast.className.replace('show', ''); }, 3000);
    };

    // --- 5. RENDER FUNCTIONS ---

    function render() {
        dom.loadingSpinner.style.display = state.isLoading ? 'block' : 'none';

        dom.viewGridBtn.classList.toggle('active', state.viewMode === 'grid');
        dom.viewTableBtn.classList.toggle('active', state.viewMode === 'table');

        const filteredAndSortedProjects = getFilteredAndSortedProjects();

        dom.projectsContainer.innerHTML = '';
        if (filteredAndSortedProjects.length > 0) {
            dom.emptyState.style.display = 'none';
            if (state.viewMode === 'grid') {
                renderGridView(filteredAndSortedProjects);
            } else {
                renderTableView(filteredAndSortedProjects);
            }
        } else {
            dom.emptyState.style.display = 'block';
        }
        lucide.createIcons();
    }

    function getFilteredAndSortedProjects() {
        let filtered = state.projects.filter(project =>
            project.name.toLowerCase().includes(state.searchTerm.toLowerCase()) ||
            (project.description && project.description.toLowerCase().includes(state.searchTerm.toLowerCase()))
        );

        if (state.sortConfig.key) {
            const { key, direction } = state.sortConfig;
            const dir = direction === 'asc' ? 1 : -1;

            filtered.sort((a, b) => {
                const aValue = a[key];
                const bValue = b[key];

                if (key === 'name' || key === 'description') {
                    return (aValue || '').localeCompare(bValue || '', 'ru', { sensitivity: 'base' }) * dir;
                }
                if (key === 'created_at' || key === 'updated_at') {
                    return (new Date(aValue) - new Date(bValue)) * dir;
                }
                if (key === 'size_kb') {
                    return (a.size_kb - b.size_kb) * dir;
                }
                if (aValue < bValue) return -1 * dir;
                if (aValue > bValue) return 1 * dir;
                return 0;
            });
        }
        return filtered;
    }

    function renderGridView(projects) {
        const grid = document.createElement('div');
        grid.className = 'projects-grid';
        projects.forEach(project => grid.appendChild(createProjectCard(project)));
        dom.projectsContainer.appendChild(grid);
    }

    function renderTableView(projects) {
        const tableWrapper = document.createElement('div');
        tableWrapper.className = 'projects-table-wrapper';
        const table = document.createElement('table');
        table.className = 'projects-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th><div data-sort-key="name">Название <i data-lucide="arrow-up-down" class="sort-icon"></i></div></th>
                    <th><div>Описание</div></th>
                    <th><div data-sort-key="size_kb">Размер <i data-lucide="arrow-up-down" class="sort-icon"></i></div></th>
                    <th><div data-sort-key="updated_at">Изменен <i data-lucide="arrow-up-down" class="sort-icon"></i></div></th>
                    <th><div>Действия</div></th>
                </tr>
            </thead>
            <tbody></tbody>
        `;
        const tbody = table.querySelector('tbody');
        projects.forEach(project => tbody.appendChild(createProjectRow(project)));
        tableWrapper.appendChild(table);
        dom.projectsContainer.appendChild(tableWrapper);
    }

    function createProjectCard(project) {
        const card = document.createElement('div');
        card.className = 'project-card';
        card.dataset.id = project.id;
        const isEditing = state.editingId === project.id;

        card.innerHTML = isEditing ? `
            <div class="card-content">
                <div class="form-group"><input type="text" value="${escapeHTML(project.name)}" class="card-title-input" name="name"></div>
                <div class="form-group"><textarea class="card-description-input" name="description" rows="3">${escapeHTML(project.description)}</textarea></div>
                <div class="card-footer"><div class="card-actions">
                    <button class="btn btn-icon save-btn" title="Сохранить"><i data-lucide="save"></i></button>
                    <button class="btn btn-icon cancel-btn" title="Отмена"><i data-lucide="x"></i></button>
                </div></div>
            </div>` : `
            <div class="card-content">
                <div class="card-header">
                    <h3 class="card-title">${escapeHTML(project.name)}</h3>
                    <div class="card-actions">
                        <button class="btn btn-icon edit-btn" title="Редактировать"><i data-lucide="edit"></i></button>
                        <button class="btn btn-icon danger delete-btn" title="Удалить"><i data-lucide="trash-2"></i></button>
                    </div>
                </div>
                <p class="card-description">${escapeHTML(project.description || 'Нет описания.')}</p>
                <div class="card-footer">
                    <span class="card-size-badge">${project.size_kb.toFixed(2)} KB</span>
                    <button class="btn btn-success card-run-btn"><i data-lucide="play"></i><span>Запустить</span></button>
                </div>
            </div>`;
        return card;
    }

    function createProjectRow(project) {
        const row = document.createElement('tr');
        row.dataset.id = project.id;
        const isEditing = state.editingId === project.id;

        row.innerHTML = isEditing ? `
            <td colspan="4">
                <div class="form-grid" style="grid-template-columns: 1fr 2fr; gap: 1rem;">
                    <div class="form-group"><label>Название</label><input type="text" value="${escapeHTML(project.name)}" class="table-edit-input" name="name"></div>
                    <div class="form-group"><label>Описание</label><input type="text" value="${escapeHTML(project.description)}" class="table-edit-input" name="description"></div>
                </div>
            </td>
            <td class="table-actions">
                <button class="btn btn-icon save-btn" title="Сохранить"><i data-lucide="save"></i></button>
                <button class="btn btn-icon cancel-btn" title="Отмена"><i data-lucide="x"></i></button>
            </td>` : `
            <td class="project-name">${escapeHTML(project.name)}</td>
            <td><div class="description-cell">${escapeHTML(project.description || '---')}</div></td>
            <td>${project.size_kb.toFixed(2)} KB</td>
            <td>${formatDate(project.updated_at)}</td>
            <td class="table-actions">
                <button class="btn btn-icon edit-btn" title="Редактировать"><i data-lucide="edit"></i></button>
                <button class="btn btn-icon danger delete-btn" title="Удалить"><i data-lucide="trash-2"></i></button>
                <button class="btn btn-icon run-btn" title="Запустить"><i data-lucide="play"></i></button>
            </td>`;
        return row;
    }

    // --- 6. EVENT HANDLERS & LOGIC ---

    function handleSort(header) {
        const key = header.dataset.sortKey;
        let direction = 'asc';
        if (state.sortConfig.key === key && state.sortConfig.direction === 'asc') {
            direction = 'desc';
        }
        state.sortConfig = { key, direction };
        render();
    }

    async function handleSaveEdit(id, projectItem) {
        const name = projectItem.querySelector('[name="name"]').value;
        const description = projectItem.querySelector('[name="description"]').value;

        try {
            const response = await api.updateProjectPartial(id, { name, description });
            if (!response.ok) throw new Error('Failed to save');
            const updatedProject = await response.json();

            state.projects = state.projects.map(p => p.id === id ? { ...p, ...updatedProject } : p);
            state.editingId = null;
            showNotification("Проект успешно обновлен.");
            render();
        } catch (error) {
            showNotification("Ошибка сохранения.", 'error');
        }
    }

    async function handleDelete(id) {
        if (!confirm("Вы уверены, что хотите удалить этот проект?")) return;
        try {
            const response = await api.deleteProject(id);
            if (!response.ok) throw new Error('Failed to delete');
            state.projects = state.projects.filter(p => p.id !== id);
            showNotification("Проект удален.");
            render();
        } catch(error) {
            showNotification("Ошибка удаления.", 'error');
        }
    }

    async function handleAddProject() {
        const name = dom.addNameInput.value.trim();
        const description = dom.addDescriptionInput.value.trim();
        if (!name) return showNotification("Название проекта не может быть пустым.", 'error');

        try {
            const response = await api.createProject({ name, description });
            if (!response.ok) throw new Error((await response.json()).detail || 'Failed to create');
            const newProject = await response.json();

            newProject.size_kb = 0; // Default size_kb as API doesn't return it
            state.projects.unshift(newProject);

            state.showAddForm = false;
            dom.addProjectFormContainer.style.display = 'none';
            dom.showAddFormBtn.style.display = 'inline-flex';
            dom.addNameInput.value = '';
            dom.addDescriptionInput.value = '';

            showNotification("Проект успешно создан.");
            render();
        } catch (error) {
            showNotification(`Ошибка создания проекта: ${error.message}`, 'error');
        }
    }

    function setupEventListeners() {
        dom.searchInput.addEventListener('input', (e) => {
            state.searchTerm = e.target.value;
            render();
        });
        dom.viewGridBtn.addEventListener('click', () => { state.viewMode = 'grid'; render(); });
        dom.viewTableBtn.addEventListener('click', () => { state.viewMode = 'table'; render(); });
        dom.showAddFormBtn.addEventListener('click', () => {
            state.showAddForm = true;
            dom.addProjectFormContainer.style.display = 'block';
            dom.showAddFormBtn.style.display = 'none';
        });
        dom.cancelAddProjectBtn.addEventListener('click', () => {
            state.showAddForm = false;
            dom.addProjectFormContainer.style.display = 'none';
            dom.showAddFormBtn.style.display = 'inline-flex';
            dom.addNameInput.value = '';
            dom.addDescriptionInput.value = '';
        });
        dom.addProjectBtn.addEventListener('click', handleAddProject);

        dom.projectsContainer.addEventListener('click', (e) => {
            const target = e.target;
            const sortHeader = target.closest('th > div[data-sort-key]');
            if (sortHeader) return handleSort(sortHeader);

            const projectItem = target.closest('.project-card, tr[data-id]');
            if (!projectItem) return;

            const id = projectItem.dataset.id;
            if (target.closest('.edit-btn')) { state.editingId = id; render(); }
            else if (target.closest('.cancel-btn')) { state.editingId = null; render(); }
            else if (target.closest('.save-btn')) handleSaveEdit(id, projectItem);
            else if (target.closest('.delete-btn')) handleDelete(id);
            else if (target.closest('.run-btn, .card-run-btn, .card-title, .project-name')) window.location.href = `/projects/${id}`;
        });
    }

    // --- 7. INITIALIZATION ---
    async function init() {
        try {
            const response = await api.getProjects();
            if (!response.ok) throw new Error('Failed to fetch projects');
            state.projects = await response.json();
        } catch (error) {
            dom.errorContainer.textContent = "Не удалось загрузить проекты.";
            dom.errorContainer.style.display = "block";
        } finally {
            state.isLoading = false;
            render();
        }
    }

    setupEventListeners();
    init();
});