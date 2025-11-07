"""
Правило для проверки корректности формата email-адреса.
"""
import re
import pandas as pd
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Проверка Email"
RULE_DESC = "Проверяет, что значение является корректным email-адресом."
IS_CONFIGURABLE = False

# Улучшенное регулярное выражение, соответствующее большинству современных стандартов
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$')

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    return RULE_NAME

def validate(value, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет формат email-адреса.

    Args:
        value: Проверяемое значение.
        params (dict, optional): Параметры правила (не используются).
        project_id (str, optional): ID проекта для логирования.

    Returns:
        dict: Словарь с результатом валидации.
              {"is_valid": bool, "errors": str|None}
    """
    if pd.isna(value) or str(value).strip() == '':
        return {"is_valid": True, "errors": None}

    s_value = str(value).strip()

    if not EMAIL_REGEX.match(s_value):
        error = "Некорректный формат email-адреса"
        # logger.debug(f"[{project_id}] {RULE_NAME}: Значение '{s_value}' не прошло проверку REGEX.")
        return {"is_valid": False, "errors": error}

    # logger.debug(f"[{project_id}] {RULE_NAME}: Значение '{s_value}' является корректным email.")
    return {"is_valid": True, "errors": None}
