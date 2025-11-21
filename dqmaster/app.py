import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json
from core.exceptions import DQMasterError, ProjectNotFoundError, SecurityError
from core.config import settings
from core.storage import status_storage
import os

# Настройка логирования
logger = logging.getLogger("dqmaster")
logger.setLevel(logging.DEBUG)

# Обработчик для основного лога
app_handler = logging.FileHandler("app.log", encoding='utf-8')
app_handler.setLevel(logging.INFO)
app_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

# Обработчик для дебаг-лога
debug_handler = logging.FileHandler("debug.log", encoding='utf-8')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)d] %(message)s'))

logger.addHandler(app_handler)
logger.addHandler(debug_handler)
logger.info("Логирование успешно инициализировано")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Инициализация приложения при запуске"""
    logger.info("=== Запуск DQMaster ===")

    # Создание необходимых директорий
    settings.STATIC_DIR.mkdir(exist_ok=True)
    settings.RULES_DIR.mkdir(exist_ok=True)
    settings.PROJECTS_DIR.mkdir(exist_ok=True)

    # Импорт и регистрация роутеров
    from api import projects, validation, rules, dictionary, rule_groups

    app.include_router(projects.router, prefix="/api")
    app.include_router(validation.router, prefix="/api")
    app.include_router(rules.router, prefix="/api")
    app.include_router(dictionary.router, prefix="/api")
    app.include_router(rule_groups.router, prefix="/api")

    # Обработчик ошибок
    @app.exception_handler(DQMasterError)
    async def dqmaster_exception_handler(request, exc):
        logger.error(f"Ошибка приложения: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )

    @app.exception_handler(SecurityError)
    async def security_exception_handler(request, exc):
        logger.error(f"Ошибка безопасности: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=403,
            content={"detail": "Обнаружено нарушение безопасности"}
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        logger.error(f"HTTP ошибка: {exc.detail}", exc_info=True)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

    logger.info("=== DQMaster запущен успешно ===")

@app.get("/")
async def read_root():
    return {"message": "DQMaster API is running"}

@app.get("/projects/{project_id}")
async def read_project_page(project_id: str):
    """Возвращает HTML-страницу проекта"""
    from core.security import SecurityValidator
    try:
        SecurityValidator.validate_project_id(project_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Неверный формат ID проекта")

    project_html_path = settings.STATIC_DIR / "project.html"
    if not project_html_path.exists():
        logger.error(f"HTML-файл проекта не найден по пути {project_html_path}")
        raise HTTPException(status_code=500, detail="Отсутствует шаблон страницы проекта")

    return FileResponse(project_html_path)

@app.get("/rules")
async def read_rules_page():
    """Возвращает HTML-страницу с правилами"""
    rules_html_path = settings.STATIC_DIR / "rules.html"
    if not rules_html_path.exists():
        logger.error(f"HTML-файл правил не найден по пути {rules_html_path}")
        raise HTTPException(status_code=500, detail="Отсутствует шаблон страницы правил")

    return FileResponse(rules_html_path)

@app.get("/dictionary")
async def read_dictionary_page():
    """Возвращает HTML-страницу словаря"""
    dictionary_html_path = settings.STATIC_DIR / "dictionary.html"
    if not dictionary_html_path.exists():
        logger.error(f"HTML-файл словаря не найден по пути {dictionary_html_path}")
        raise HTTPException(status_code=500, detail="Отсутствует шаблон страницы словаря")

    return FileResponse(dictionary_html_path)

@app.get("/rule-groups")
async def read_rule_groups_page():
    """Возвращает HTML-страницу групп правил"""
    rule_groups_html_path = settings.STATIC_DIR / "rule_groups.html"
    if not rule_groups_html_path.exists():
        logger.error(f"HTML-файл групп правил не найден по пути {rule_groups_html_path}")
        raise HTTPException(status_code=500, detail="Отсутствует шаблон страницы групп правил")

    return FileResponse(rule_groups_html_path)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
