"""
Правило для проверки, что значение начинается с заглавной буквы или цифры.
"""
import re
import pandas as pd
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Начинается с заглавной"
RULE_DESC = "Проверяет, что значение начинается с заглавной буквы или цифры, игнорируя пробелы и знаки препинания в начале."
IS_CONFIGURABLE = False

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    return RULE_NAME

def validate(value, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет, что значение начинается с заглавной буквы или цифры.

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

    s_value = str(value)

    # Ищем первый буквенно-цифровой символ
    match = re.search(r'\\w', s_value)

    if not match:
        # Строка состоит только из пробелов или знаков препинания
        # logger.debug(f"[{project_id}] {RULE_NAME}: В '{s_value}' не найдено буквенно-цифровых символов.")
        return {"is_valid": True, "errors": None}

    first_char = match.group(0)

    if not (first_char.isupper() or first_char.isdigit()):
        error = "Значение должно начинаться с заглавной буквы или цифры"
        # logger.debug(f"[{project_id}] {RULE_NAME}: Первый символ '{first_char}' в '{s_value}' не является заглавной буквой или цифрой.")
        return {"is_valid": False, "errors": error}

    # logger.debug(f"[{project_id}] {RULE_NAME}: Значение '{s_value}' прошло проверку.")
    return {"is_valid": True, "errors": None}
