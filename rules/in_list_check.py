import pandas as pd

RULE_NAME = "Значение в списке"
RULE_DESC = "Проверяет, что значение присутствует в заданном списке допустимых значений."
IS_CONFIGURABLE = True

PARAMS_SCHEMA = [
    {
        "name": "allowed_values",
        "type": "text",
        "label": "Список допустимых значений (через запятую)",
        "default": ""
    },
    {
        "name": "case_sensitive",
        "type": "checkbox",
        "label": "Учитывать регистр",
        "default": False
    }
]

def format_name(params):
    if not params or not params.get("allowed_values"):
        return RULE_NAME
    return "Значение в списке"

def validate(value, params=None):
    if pd.isna(value) or not params or not params.get("allowed_values"):
        return True
    allowed_values_str = params.get("allowed_values", "")
    case_sensitive = params.get("case_sensitive", False)
    allowed_list = [item.strip() for item in allowed_values_str.split(',')]
    s_value = str(value)
    if case_sensitive:
        return s_value in allowed_list
    else:
        return s_value.lower() in [item.lower() for item in allowed_list]