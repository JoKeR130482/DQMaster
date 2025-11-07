"""
Правило для проверки уникальности значений в столбце.
"""
import pandas as pd
import logging

logger = logging.getLogger("dqmaster")

# --- Описание правила ---
RULE_NAME = "Уникальное значение"
RULE_DESC = "Проверяет, что все значения в столбце являются уникальными."
NEEDS_COLUMN_ACCESS = True
IS_CONFIGURABLE = True
PARAMS_SCHEMA = [
    {
        "name": "case_sensitive",
        "type": "checkbox",
        "label": "Учитывать регистр",
        "default": True
    }
]

def format_name(params: dict = None) -> str:
    """
    Форматирует имя правила с учетом параметров.
    """
    if params and not params.get("case_sensitive", True):
        return f"{RULE_NAME} (без учета регистра)"
    return f"{RULE_NAME} (с учетом регистра)"

def validate_column(column: pd.Series, params: dict = None, project_id: str = None) -> dict:
    """
    Проверяет уникальность значений в столбце.

    Args:
        column (pd.Series): Столбец данных для проверки.
        params (dict, optional): Параметры правила.
                                 'case_sensitive' (bool): Учитывать ли регистр.
        project_id (str, optional): ID проекта для логирования.

    Returns:
        dict: Словарь с результатом валидации, содержащий списки.
              {"is_valid": list[bool], "errors": list[str|None]}
    """
    case_sensitive = params.get("case_sensitive", True) if params else True

    # Игнорируем пустые значения, они не участвуют в проверке на уникальность
    non_empty_column = column.dropna().astype(str).str.strip()
    non_empty_column = non_empty_column[non_empty_column != '']

    if non_empty_column.empty:
        # logger.debug(f"[{project_id}] {RULE_NAME}: столбец не содержит непустых значений.")
        return {"is_valid": [True] * len(column), "errors": [None] * len(column)}

    check_series = non_empty_column
    if not case_sensitive:
        check_series = non_empty_column.str.lower()

    # Находим дубликаты
    duplicates = check_series.duplicated(keep=False)

    # Создаем карту индексов оригинального столбца для дубликатов
    duplicate_map = non_empty_column[duplicates].index

    # Собираем результат
    is_valid_list = [True] * len(column)
    errors_list = [None] * len(column)

    for idx in duplicate_map:
        is_valid_list[idx] = False
        errors_list[idx] = "Значение не уникально в этом столбце"

    num_duplicates = duplicates.sum()
    # logger.debug(f"[{project_id}] {RULE_NAME}: Найдено {num_duplicates} дубликатов (case_sensitive={case_sensitive}).")

    return {"is_valid": is_valid_list, "errors": errors_list}

def validate(value, params=None):
    """
    Эта функция-заглушка не должна вызываться, так как правило требует доступ к столбцу.
    """
    # logger.warning("Функция validate для правила unique_value была вызвана, хотя она требует доступа к столбцу.")
    return {"is_valid": False, "errors": "Ошибка конфигурации правила"}
