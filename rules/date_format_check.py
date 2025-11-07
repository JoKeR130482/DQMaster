"""
Правило для проверки соответствия значения заданному формату даты.
"""
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Проверка формата даты"
RULE_DESC = "Проверяет, соответствует ли значение указанному формату даты (например, %Y-%m-%d)."
IS_CONFIGURABLE = True
PARAMS_SCHEMA = [
    {
        "name": "date_format",
        "type": "text",
        "label": "Формат даты",
        "placeholder": "%Y-%m-%d %H:%M:%S",
        "default": "%Y-%m-%d"
    }
]

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    if params and params.get("date_format"):
        return f"{RULE_NAME} (формат: {params['date_format']})"
    return RULE_NAME

def validate(value, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет формат даты.

    Args:
        value: Проверяемое значение.
        params (dict, optional): Параметры правила.
                                 'date_format' (str): Ожидаемый формат даты.
        project_id (str, optional): ID проекта для логирования.

    Returns:
        dict: Словарь с результатом валидации.
              {"is_valid": bool, "errors": str|None}
    """
    if pd.isna(value) or str(value).strip() == '':
        # Пустые значения считаются валидными, т.к. для обязательных полей есть правило is_empty
        return {"is_valid": True, "errors": None}

    if not params or not params.get("date_format"):
        error = "Не указан формат даты для проверки в параметрах правила"
        # logger.warning(f"[{project_id}] {RULE_NAME}: {error}")
        return {"is_valid": False, "errors": error}

    date_format = params.get("date_format")
    s_value = str(value)

    try:
        datetime.strptime(s_value, date_format)
        # logger.debug(f"[{project_id}] {RULE_NAME}: Значение '{s_value}' соответствует формату '{date_format}'")
        return {"is_valid": True, "errors": None}
    except (ValueError, TypeError):
        error = f"Дата '{s_value}' не соответствует формату '{date_format}'"
        # logger.debug(f"[{project_id}] {RULE_NAME}: {error}")
        return {"is_valid": False, "errors": error}
