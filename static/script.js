document.addEventListener('DOMContentLoaded', () => {
    // --- 1. DOM Elements ---
    const loadingSpinner = document.getElementById('loading');
    const createProjectBtn = document.getElementById('create-project-btn');
    const projectsTbody = document.getElementById('projects-tbody');
    const noProjectsMessage = document.getElementById('no-projects-message');

    // Create Project Modal Elements
    const createProjectModal = document.getElementById('create-project-modal');
    const projectNameInput = document.getElementById('project-name-input');
    const projectDescriptionInput = document.getElementById('project-description-input');
    const confirmCreateProjectBtn = document.getElementById('confirm-create-project-btn');
    const cancelCreateProjectBtn = document.getElementById('cancel-create-project-btn');

    // Edit Project Modal Elements
    const editProjectModal = document.getElementById('edit-project-modal');
    const editProjectIdInput = document.getElementById('edit-project-id');
    const editProjectNameInput = document.getElementById('edit-project-name-input');
    const editProjectDescriptionInput = document.getElementById('edit-project-description-input');
    const confirmEditProjectBtn = document.getElementById('confirm-edit-project-btn');
    const cancelEditProjectBtn = document.getElementById('cancel-edit-project-btn');

    // Notification Toast
    const notificationToast = document.getElementById('notification-toast');

    // --- 2. Helper Functions ---
    const showNotification = (message, type = 'success') => {
        notificationToast.textContent = message;
        notificationToast.className = `toast show ${type}`;
        setTimeout(() => {
            notificationToast.className = notificationToast.className.replace('show', '');
        }, 3000);
    };

    const formatDate = (isoString) => {
        if (!isoString) return 'N/A';
        const date = new Date(isoString);
        return date.toLocaleString('ru-RU', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    // --- 3. Core Functions ---

    const fetchAndRenderProjects = async () => {
        loadingSpinner.style.display = 'block';
        projectsTbody.innerHTML = '';
        noProjectsMessage.style.display = 'none';

        try {
            const response = await fetch('/api/projects');
            if (!response.ok) {
                throw new Error('Не удалось загрузить проекты');
            }
            const projects = await response.json();

            if (projects.length === 0) {
                noProjectsMessage.style.display = 'block';
            } else {
                renderProjects(projects);
            }
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            loadingSpinner.style.display = 'none';
        }
    };

    const renderProjects = (projects) => {
        const projectsContainer = document.getElementById('projects-tbody');
        projectsContainer.innerHTML = ''; // Clear previous entries
        projects.forEach(project => {
            const card = document.createElement('div');
            card.className = 'project-card';
            card.dataset.projectId = project.id;

            card.innerHTML = `
                <a href="/projects/${project.id}" class="project-card-link"></a>
                <div class="project-card-header">
                    <h2 class="project-card-name">${project.name}</h2>
                </div>
                <div class="project-card-body">
                    <p class="project-card-description">${project.description || 'Нет описания.'}</p>
                </div>
                <div class="project-card-footer">
                    <div class="project-card-meta">
                        <span>${formatDate(project.updated_at)}</span>
                        <span>${project.size_kb} KB</span>
                    </div>
                    <div class="project-card-actions">
                        <button class="edit-project-btn" data-project-id="${project.id}" data-project-name="${project.name}" data-project-description="${project.description || ''}">Править</button>
                        <button class="delete-project-btn" data-project-id="${project.id}" data-project-name="${project.name}">Удалить</button>
                    </div>
                </div>
            `;
            projectsContainer.appendChild(card);
        });
    };

    const openCreateProjectModal = () => {
        projectNameInput.value = '';
        projectDescriptionInput.value = '';
        createProjectModal.style.display = 'flex';
        projectNameInput.focus();
    };

    const closeCreateProjectModal = () => {
        createProjectModal.style.display = 'none';
    };

    const handleCreateProject = async () => {
        const name = projectNameInput.value.trim();
        const description = projectDescriptionInput.value.trim();

        if (!name) {
            showNotification('Название проекта не может быть пустым.', 'error');
            return;
        }

        confirmCreateProjectBtn.disabled = true;

        try {
            const response = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Не удалось создать проект');
            }

            const newProject = await response.json();
            showNotification('Проект успешно создан! Перенаправление...', 'success');

            // Redirect to the new project's page
            window.location.href = `/projects/${newProject.id}`;

        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            confirmCreateProjectBtn.disabled = false;
        }
    };

    const handleDeleteProject = async (projectId, projectName) => {
        if (!confirm(`Вы уверены, что хотите удалить проект "${projectName}"? Это действие необратимо.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Не удалось удалить проект');
            }

            showNotification(`Проект "${projectName}" успешно удален.`, 'success');
            await fetchAndRenderProjects();

        } catch (error) {
            showNotification(error.message, 'error');
        }
    };


    const openEditProjectModal = (id, name, description) => {
        editProjectIdInput.value = id;
        editProjectNameInput.value = name;
        editProjectDescriptionInput.value = description;
        editProjectModal.style.display = 'flex';
        editProjectNameInput.focus();
    };

    const closeEditProjectModal = () => {
        editProjectModal.style.display = 'none';
    };

    const handleEditProject = async () => {
        const id = editProjectIdInput.value;
        const name = editProjectNameInput.value.trim();
        const description = editProjectDescriptionInput.value.trim();

        if (!name) {
            showNotification('Название проекта не может быть пустым.', 'error');
            return;
        }

        confirmEditProjectBtn.disabled = true;

        try {
            const response = await fetch(`/api/projects/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Не удалось обновить проект');
            }

            const updatedProject = await response.json();

            showNotification('Проект успешно обновлен!', 'success');
            closeEditProjectModal();

            // Instead of a full re-render, update the specific card in-place
            const cardToUpdate = document.querySelector(`.project-card[data-project-id="${id}"]`);
            if (cardToUpdate) {
                cardToUpdate.querySelector('.project-card-name').textContent = updatedProject.name;
                cardToUpdate.querySelector('.project-card-description').textContent = updatedProject.description || 'Нет описания.';

                // Update meta info
                const meta = cardToUpdate.querySelector('.project-card-meta');
                meta.children[0].textContent = formatDate(updatedProject.updated_at);

                // Update the dataset for the buttons
                const editButton = cardToUpdate.querySelector('.edit-project-btn');
                if (editButton) {
                    editButton.dataset.projectName = updatedProject.name;
                    editButton.dataset.projectDescription = updatedProject.description || '';
                }
                const deleteButton = cardToUpdate.querySelector('.delete-project-btn');
                 if (deleteButton) {
                    deleteButton.dataset.projectName = updatedProject.name;
                }
            } else {
                // As a fallback if the card isn't found, just re-render the whole list
                fetchAndRenderProjects();
            }

        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            confirmEditProjectBtn.disabled = false;
        }
    };


    // --- 4. Event Listeners ---
    createProjectBtn.addEventListener('click', openCreateProjectModal);
    cancelCreateProjectBtn.addEventListener('click', closeCreateProjectModal);
    confirmCreateProjectBtn.addEventListener('click', handleCreateProject);

    cancelEditProjectBtn.addEventListener('click', closeEditProjectModal);
    confirmEditProjectBtn.addEventListener('click', handleEditProject);

    projectsTbody.addEventListener('click', (event) => {
        const button = event.target;
        if (button.classList.contains('delete-project-btn')) {
            const projectId = button.dataset.projectId;
            const projectName = button.dataset.projectName;
            handleDeleteProject(projectId, projectName);
        } else if (button.classList.contains('edit-project-btn')) {
            const projectId = button.dataset.projectId;
            const projectName = button.dataset.projectName;
            const projectDescription = button.dataset.projectDescription;
            openEditProjectModal(projectId, projectName, projectDescription);
        }
    });

    // --- 5. Initial Load ---
    fetchAndRenderProjects();
});