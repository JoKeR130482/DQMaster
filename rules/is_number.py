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
    if not params:
        return RULE_NAME
    num_type = params.get("number_type", "any")
    if num_type == 'integer':
        return "Значение должно быть целым числом"
    if num_type == 'float':
        return "Значение должно быть дробным числом"
    return RULE_NAME

def validate(value, params=None):
    if pd.isna(value) or value == '':
        return True
    num_type = params.get("number_type", "any") if params else "any"
    try:
        num_value = float(value)
    except (ValueError, TypeError):
        return False
    if num_type == 'integer':
        return num_value == int(num_value)
    elif num_type == 'float':
        if isinstance(value, str) and '.' in value:
            return True
        return num_value != int(num_value)
    return True