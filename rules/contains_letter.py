"""
Правило для проверки наличия хотя бы одной буквы в значении.
"""
import pandas as pd
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Содержит букву"
RULE_DESC = "Проверяет, что значение содержит хотя бы одну букву."
IS_CONFIGURABLE = True
PARAMS_SCHEMA = [
    {
        "name": "allow_empty",
        "type": "checkbox",
        "label": "Разрешить пустые значения",
        "default": True
    }
]

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    if params and not params.get("allow_empty", True):
        return f"{RULE_NAME} (обязательное)"
    return RULE_NAME

def validate(value, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет наличие буквы в значении.

    Args:
        value: Проверяемое значение.
        params (dict, optional): Параметры правила.
                                 'allow_empty' (bool): Разрешить ли пустые значения.
        project_id (str, optional): ID проекта для логирования.

    Returns:
        dict: Словарь с результатом валидации.
              {"is_valid": bool, "errors": str|None}
    """
    allow_empty = params.get("allow_empty", True) if params else True

    if pd.isna(value) or str(value).strip() == '':
        is_valid = allow_empty
        error = None if is_valid else "Значение не должно быть пустым"
        # logger.debug(f"[{project_id}] {RULE_NAME}: Пустое значение, allow_empty={allow_empty}, результат: {is_valid}")
        return {"is_valid": is_valid, "errors": error}

    s_value = str(value)
    has_letter = any(char.isalpha() for char in s_value)

    if not has_letter:
        error = "Значение должно содержать хотя бы одну букву"
        # logger.debug(f"[{project_id}] {RULE_NAME}: В значении '{s_value}' не найдено букв.")
        return {"is_valid": False, "errors": error}

    # logger.debug(f"[{project_id}] {RULE_NAME}: В значении '{s_value}' найдена буква.")
    return {"is_valid": True, "errors": None}
