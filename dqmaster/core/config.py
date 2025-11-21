from pathlib import Path
from typing import Optional
import os

class Settings:
    """Конфигурация приложения"""

    # Базовая директория
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Директории
    STATIC_DIR: Path = BASE_DIR / "static"
    RULES_DIR: Path = BASE_DIR / "rules"
    PROJECTS_DIR: Path = BASE_DIR / "projects"

    # Файлы
    RULE_GROUPS_PATH: Path = BASE_DIR / "rule_groups.json"
    CUSTOM_DICT_PATH: Path = BASE_DIR / "custom_dictionary.txt"

    # Ограничения
    MAX_FILE_SIZE: int = 100 * 1024 * 1024 # 100MB
    MAX_EXCEL_ROWS: int = 1_000_000
    MAX_PROJECTS: int = 1000

    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def __init__(self):
        # Создаем необходимые директории при инициализации
        self.STATIC_DIR.mkdir(exist_ok=True)
        self.RULES_DIR.mkdir(exist_ok=True)
        self.PROJECTS_DIR.mkdir(exist_ok=True)

        # Создаем файлы, если не существуют
        if not self.RULE_GROUPS_PATH.exists():
            self.RULE_GROUPS_PATH.write_text("[]", encoding="utf-8")

        if not self.CUSTOM_DICT_PATH.exists():
            self.CUSTOM_DICT_PATH.touch()

# Глобальный экземпляр настроек
settings = Settings()
