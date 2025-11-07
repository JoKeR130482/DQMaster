"""
Правило для проверки отсутствия пробелов в начале и в конце значения.
"""
import pandas as pd
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Без начальных/конечных пробелов"
RULE_DESC = "Проверяет, что значение не содержит пробелов в начале или в конце."
IS_CONFIGURABLE = False

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    return RULE_NAME

def validate(value, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет отсутствие начальных и конечных пробелов.

    Args:
        value: Проверяемое значение.
        params (dict, optional): Параметры правила (не используются).
        project_id (str, optional): ID проекта для логирования.

    Returns:
        dict: Словарь с результатом валидации.
              {"is_valid": bool, "errors": str|None}
    """
    if pd.isna(value):
        return {"is_valid": True, "errors": None}

    s_value = str(value)

    # Пустая строка или строка из пробелов не имеет начальных/конечных пробелов в контексте этого правила
    if s_value.strip() == '':
        return {"is_valid": True, "errors": None}

    if s_value != s_value.strip():
        starts_with_space = s_value.startswith(' ')
        ends_with_space = s_value.endswith(' ')

        if starts_with_space and ends_with_space:
            error = "Значение содержит пробелы в начале и в конце"
        elif starts_with_space:
            error = "Значение содержит пробелы в начале"
        else:
            error = "Значение содержит пробелы в конце"

        # logger.debug(f"[{project_id}] {RULE_NAME}: Ошибка в '{s_value}': {error}")
        return {"is_valid": False, "errors": error}

    # logger.debug(f"[{project_id}] {RULE_NAME}: Значение '{s_value}' прошло проверку.")
    return {"is_valid": True, "errors": None}
