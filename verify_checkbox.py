
import asyncio
from playwright.async_api import async_playwright, expect
import uuid
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

async def main():
    """
    Основная функция для запуска теста Playwright.
    - Создает уникальный проект через API.
    - Открывает страницу проекта.
    - Проверяет, что чекбокс "Авто-перепроверка" ИЗНАЧАЛЬНО СНЯТ.
    - Кликает на чекбокс, чтобы активировать его.
    - Проверяет, что чекбокс стал АКТИВНЫМ.
    - Перезагружает страницу.
    - Проверяет, что чекбокс ОСТАЛСЯ АКТИВНЫМ после перезагрузки.
    - Кликает на чекбокс снова, чтобы деактивировать.
    - Проверяет, что он СНОВА СНЯТ.
    - Перезагружает страницу.
    - Проверяет, что он ОСТАЛСЯ СНЯТЫМ.
    - Удаляет проект через API в конце.
    """
    project_name = f"verify-checkbox-test-{uuid.uuid4()}"
    project_id = ""

    # --- 1. Создание проекта через API ---
    try:
        response = requests.post(
            f"{BASE_URL}/api/projects",
            json={"name": project_name, "description": "Test project for checkbox verification"}
        )
        response.raise_for_status()
        project_data = response.json()
        project_id = project_data["id"]
        print(f"Успешно создан проект '{project_name}' с ID: {project_id}")
    except requests.RequestException as e:
        print(f"Не удалось создать проект через API: {e}")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # --- 2. Первоначальная загрузка и проверка состояния ---
            print(f"Открытие страницы проекта: {BASE_URL}/projects/{project_id}")
            await page.goto(f"{BASE_URL}/projects/{project_id}")

            await expect(page.locator("#project-name-header")).to_contain_text(project_name)

            auto_revalidate_checkbox = page.locator("#auto-revalidate-toggle")

            print("Проверка: чекбокс по умолчанию должен быть СНЯТ.")
            await expect(auto_revalidate_checkbox).not_to_be_checked()
            print("...Успешно. Чекбокс по умолчанию снят.")

            # --- 3. Активация и проверка сохранения ---
            print("Действие: Клик по чекбоксу для активации.")
            await auto_revalidate_checkbox.check()

            print("Проверка: чекбокс должен стать АКТИВНЫМ.")
            await expect(auto_revalidate_checkbox).to_be_checked()
            print("...Успешно. Чекбокс активирован.")

            print("Действие: Перезагрузка страницы.")
            await page.reload()
            await expect(page.locator("#project-name-header")).to_contain_text(project_name)

            print("Проверка: чекбокс должен ОСТАТЬСЯ АКТИВНЫМ после перезагрузки.")
            await expect(auto_revalidate_checkbox).to_be_checked()
            print("...Успешно. Состояние сохранилось (активно).")

            # --- 4. Деактивация и проверка сохранения ---
            print("Действие: Клик по чекбоксу для деактивации.")
            await auto_revalidate_checkbox.uncheck()

            print("Проверка: чекбокс должен стать СНЯТЫМ.")
            await expect(auto_revalidate_checkbox).not_to_be_checked()
            print("...Успешно. Чекбокс деактивирован.")

            print("Действие: Перезагрузка страницы.")
            await page.reload()
            await expect(page.locator("#project-name-header")).to_contain_text(project_name)

            print("Проверка: чекбокс должен ОСТАТЬСЯ СНЯТЫМ после перезагрузки.")
            await expect(auto_revalidate_checkbox).not_to_be_checked()
            print("...Успешно. Состояние сохранилось (неактивно).")

            print("\n[УСПЕХ] Все тесты для чекбокса 'Авто-перепроверка' пройдены!")

        except Exception as e:
            print(f"\n[ОШИБКА] Тест не пройден: {e}")
            await page.screenshot(path="verify_checkbox_error.png")
            print("Скриншот ошибки сохранен в 'verify_checkbox_error.png'")
        finally:
            await browser.close()
            # --- 5. Очистка (удаление проекта) ---
            try:
                print(f"Очистка: удаление проекта с ID: {project_id}")
                response = requests.delete(f"{BASE_URL}/api/projects/{project_id}")
                response.raise_for_status()
                print("Проект успешно удален.")
            except requests.RequestException as e:
                print(f"Не удалось удалить проект '{project_id}': {e}")


if __name__ == "__main__":
    time.sleep(2)
    asyncio.run(main())
