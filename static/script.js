document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('fileInput');
    const fileLabel = document.querySelector('.file-label');
    const loadingSpinner = document.getElementById('loading');
    const resultContainer = document.getElementById('result-container');
    const columnsList = document.getElementById('columnsList');
    const errorContainer = document.getElementById('error-container');

    fileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) {
            return;
        }

        // Update file label with the selected file name
        fileLabel.textContent = file.name;

        // Reset UI
        loadingSpinner.style.display = 'block';
        resultContainer.style.display = 'none';
        errorContainer.style.display = 'none';
        columnsList.innerHTML = '';
        errorContainer.textContent = '';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload/', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            loadingSpinner.style.display = 'none';

            if (response.ok && data.columns) {
                // Success
                resultContainer.style.display = 'block';
                data.columns.forEach(column => {
                    const li = document.createElement('li');
                    li.textContent = column;
                    columnsList.appendChild(li);
                });
            } else {
                // Handle server-side errors
                const errorMessage = data.error || 'Произошла неизвестная ошибка.';
                errorContainer.textContent = `Ошибка: ${errorMessage}`;
                errorContainer.style.display = 'block';
            }
        } catch (error) {
            // Handle network or other fetch errors
            loadingSpinner.style.display = 'none';
            errorContainer.textContent = `Сетевая ошибка: ${error.message}`;
            errorContainer.style.display = 'block';
        }
    });
});