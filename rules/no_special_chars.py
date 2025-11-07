"""
Правило для проверки отсутствия в значении специальных символов.
"""
import re
import pandas as pd
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Без спецсимволов"
RULE_DESC = "Проверяет, что значение не содержит специальных символов, кроме разрешенных."
IS_CONFIGurable = True
PARAMS_SCHEMA = [
    {
        "name": "allowed_chars",
        "type": "text",
        "label": "Разрешенные символы",
        "placeholder": "-_.",
        "default": "-_."
    }
]

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    if params and params.get("allowed_chars"):
        return f"{RULE_NAME} (разрешены: '{params['allowed_chars']}')"
    return RULE_NAME

def validate(value, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет отсутствие специальных символов.

    Args:
        value: Проверяемое значение.
        params (dict, optional): Параметры правила.
                                 'allowed_chars' (str): Строка с разрешенными символами.
        project_id (str, optional): ID проекта для логирования.

    Returns:
        dict: Словарь с результатом валидации.
              {"is_valid": bool, "errors": str|None}
    """
    if pd.isna(value) or str(value).strip() == '':
        return {"is_valid": True, "errors": None}

    s_value = str(value)
    allowed_chars = params.get("allowed_chars", "-_.") if params else "-_."

    # Паттерн для поиска любых символов, кроме:
    # \\w -> a-zA-Z0-9_ (английские буквы, цифры, нижнее подчеркивание)
    # \\s -> пробельные символы
    # а-яА-ЯёЁ -> русские буквы
    # {} -> дополнительно разрешенные символы
    # re.escape используется для безопасной вставки разрешенных символов в паттерн
    pattern = r'[^\\w\\sа-яА-ЯёЁ' + re.escape(allowed_chars) + r']'
    special_chars = re.findall(pattern, s_value)

    if special_chars:
        unique_chars = ", ".join(sorted(list(set(special_chars))))
        error = f"Обнаружены запрещенные символы: {unique_chars}"
        # logger.debug(f"[{project_id}] {RULE_NAME}: В '{s_value}' найдены символы: {unique_chars}")
        return {"is_valid": False, "errors": error}

    # logger.debug(f"[{project_id}] {RULE_NAME}: В '{s_value}' запрещенных символов не найдено.")
    return {"is_valid": True, "errors": None}
