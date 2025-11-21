import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from core.exceptions import DQMasterError

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

# Обработчик ошибок
@app.exception_handler(DQMasterError)
async def dqmaster_exception_handler(request, exc):
    logger.error(f"Ошибка приложения: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

@app.on_event("startup")
async def startup_event():
    """Инициализация приложения при запуске"""
    logger.info("=== Запуск DQMaster ===")

    # Импортируем настройки
    from core.config import settings

    # Регистрация роутеров будет добавлена на следующих этапах

    logger.info("=== DQMaster запущен успешно ===")

@app.get("/")
async def read_root():
    return {"message": "DQMaster API is running"}

# Подключение статических файлов будет добавлено на следующих этапах
