document.addEventListener('DOMContentLoaded', () => {
    const createFolderBtn = document.getElementById('create-test-folder-btn');
    const notificationToast = document.getElementById('notification-toast');

    const showNotification = (message, type = 'success') => {
        notificationToast.textContent = message;
        notificationToast.className = `toast ${type}`;
        notificationToast.style.opacity = '1';

        setTimeout(() => {
            notificationToast.style.opacity = '0';
        }, 4000);
    };

    createFolderBtn.addEventListener('click', async () => {
        console.log("--- КЛИЕНТ: Кнопка нажата. Отправляю запрос на /api/create-test-folder ---");
        try {
            const response = await fetch('/api/create-test-folder', {
                method: 'POST',
            });

            const result = await response.json();

            if (!response.ok) {
                console.error("--- КЛИЕНТ: Ошибка от сервера ---", result);
                throw new Error(result.detail || 'Неизвестная ошибка сервера');
            }

            console.log("--- КЛИЕНТ: Успешный ответ от сервера ---", result);
            showNotification(result.message, 'success');

        } catch (error) {
            console.error("--- КЛИЕНТ: КРИТИЧЕСКАЯ ОШИБКА FETCH ---", error);
            showNotification(error.message, 'error');
        }
    });
});