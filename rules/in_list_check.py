"""
Правило для проверки вхождения значения в заданный список.
"""
import pandas as pd
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Значение из списка"
RULE_DESC = "Проверяет, что значение присутствует в заданном списке разрешенных значений."
IS_CONFIGURABLE = True
PARAMS_SCHEMA = [
    {
        "name": "allowed_values",
        "type": "text",
        "label": "Разрешенные значения (через запятую)",
        "placeholder": "значение1, значение2, значение3"
    },
    {
        "name": "case_sensitive",
        "type": "checkbox",
        "label": "Учитывать регистр",
        "default": False
    }
]

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    if params and params.get("allowed_values"):
        sample_values = ', '.join(params['allowed_values'].split(',')[:2])
        more = '...' if len(params['allowed_values'].split(',')) > 2 else ''
        return f"{RULE_NAME} ([{sample_values}{more}])"
    return RULE_NAME

def validate(value, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет вхождение значения в список.

    Args:
        value: Проверяемое значение.
        params (dict, optional): Параметры правила.
                                 'allowed_values' (str): Список разрешенных значений через запятую.
                                 'case_sensitive' (bool): Учитывать ли регистр.
        project_id (str, optional): ID проекта для логирования.

    Returns:
        dict: Словарь с результатом валидации.
              {"is_valid": bool, "errors": str|None}
    """
    if pd.isna(value) or str(value).strip() == '':
        return {"is_valid": True, "errors": None}

    if not params or not params.get("allowed_values"):
        error = "Не указан список разрешенных значений в параметрах правила"
        # logger.warning(f"[{project_id}] {RULE_NAME}: {error}")
        return {"is_valid": False, "errors": error}

    allowed_values_str = params.get("allowed_values", "")
    case_sensitive = params.get("case_sensitive", False)

    if not allowed_values_str.strip():
        error = "Список разрешенных значений пуст"
        # logger.warning(f"[{project_id}] {RULE_NAME}: {error}")
        return {"is_valid": False, "errors": error}

    allowed_list = [item.strip() for item in allowed_values_str.split(',') if item.strip()]
    s_value = str(value).strip()

    if case_sensitive:
        is_in_list = s_value in allowed_list
    else:
        is_in_list = s_value.lower() in [item.lower() for item in allowed_list]

    if not is_in_list:
        sample_values = ', '.join(allowed_list[:3])
        more = '...' if len(allowed_list) > 3 else ''
        error = f"Значение '{s_value}' не входит в список разрешенных: {sample_values}{more}"
        # logger.debug(f"[{project_id}] {RULE_NAME}: {error}")
        return {"is_valid": False, "errors": error}

    # logger.debug(f"[{project_id}] {RULE_NAME}: Значение '{s_value}' найдено в списке.")
    return {"is_valid": True, "errors": None}
