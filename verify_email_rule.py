import asyncio
import os
import shutil
import time  # Импортируем time для задержки
from playwright.async_api import async_playwright

PROJECT_ID_TO_TEST = "prj_2d66a485"
APP_URL = "http://127.0.0.1:8000"

async def main():
    """
    Основная функция для запуска теста Playwright с задержкой и логированием.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))

        try:
            # --- ДОБАВЛЕНО: Задержка перед началом теста ---
            print("Ждем 2 секунды, чтобы сервер точно запустился...")
            time.sleep(2)

            project_url = f"{APP_URL}/projects/{PROJECT_ID_TO_TEST}"
            print(f"Переход на страницу проекта: {project_url}")
            await page.goto(project_url)

            await page.wait_for_selector('.field-card', timeout=10000)

            field_selector = f'.field-card[data-field-id="field_f139d678"]'
            add_rule_button_selector = f'{field_selector} .add-rule-btn'
            await page.click(add_rule_button_selector)
            await page.wait_for_selector('#rule-editor-modal', state='visible')

            await page.select_option('#rule-type-select', 'rule:is_email')
            await page.wait_for_selector('#param-allow_empty')

            await page.check('#param-allow_empty')
            await page.fill('#param-domain_whitelist', 'example.com, test.org')

            await page.screenshot(path="screenshot-1-modal.png")
            await page.click('#save-rule-btn')
            await page.wait_for_selector('#rule-editor-modal', state='hidden')
            await page.wait_for_selector(f'{field_selector} .rule-item')
            await page.screenshot(path="screenshot-2-rule-list.png")

            print("\n--- Верификация прошла успешно! ---")

        except Exception as e:
            print(f"\n--- Ошибка во время верификации ---")
            print(f"Произошла ошибка: {e}")
            await page.screenshot(path="error_screenshot.png")
            print("Сделан скриншот ошибки: error_screenshot.png")

        finally:
            await browser.close()
            project_dir = os.path.join("projects", PROJECT_ID_TO_TEST)
            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)
                print(f"Тестовый проект {PROJECT_ID_TO_TEST} удален.")

if __name__ == "__main__":
    asyncio.run(main())
