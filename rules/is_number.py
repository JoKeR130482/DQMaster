import pandas as pd

RULE_NAME = "Значение должно быть числом"
RULE_DESC = "Проверяет, является ли значение целым или дробным числом."
IS_CONFIGURABLE = True

PARAMS_SCHEMA = [
    {
        "name": "number_type",
        "type": "select",
        "label": "Тип числа",
        "default": "any",
        "options": [
            {"value": "any", "label": "Любое (целое или дробное)"},
            {"value": "integer", "label": "Только целое"},
            {"value": "float", "label": "Только дробное"}
        ]
    }
]

def format_name(params):
    """Форматирует имя правила для отображения в интерфейсе."""
    if not params:
        return RULE_NAME

    num_type = params.get("number_type", "any")

    if num_type == 'integer':
        return "Значение должно быть целым числом"
    if num_type == 'float':
        return "Значение должно быть дробным числом"

    return RULE_NAME


def validate(value, params=None):
    """
    Проверяет, является ли значение числом указанного типа.
    """
    if pd.isna(value) or value == '':
        return True # Пустые значения пропускаем

    num_type = params.get("number_type", "any") if params else "any"

    # Попытка преобразовать в float в любом случае
    try:
        num_value = float(value)
    except (ValueError, TypeError):
        return False # Если не удалось преобразовать в float, это точно не число

    if num_type == 'integer':
        # Проверяем, является ли число целым (num_value == int(num_value))
        return num_value == int(num_value)
    elif num_type == 'float':
        # Если нужно именно дробное, то оно не должно быть целым
        # Исключение: если значение было строкой с точкой, например "123.0"
        if isinstance(value, str) and '.' in value:
            return True
        return num_value != int(num_value)

    # Для типа 'any' достаточно того, что оно успешно преобразовалось в float
    return True