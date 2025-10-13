import pandas as pd

RULE_NAME = "Проверка длины строки"
RULE_DESC = "Проверяет, что длина значения находится в заданном диапазоне."
IS_CONFIGURABLE = True

PARAMS_SCHEMA = [
    {
        "name": "min_length",
        "type": "text",
        "label": "Минимальная длина (включительно)",
        "default": "0"
    },
    {
        "name": "max_length",
        "type": "text",
        "label": "Максимальная длина (включительно)",
        "default": ""
    }
]

def format_name(params):
    if not params:
        return RULE_NAME
    min_len = params.get("min_length")
    max_len = params.get("max_length")
    if min_len and max_len:
        return f"Длина от {min_len} до {max_len} симв."
    if min_len:
        return f"Длина не менее {min_len} симв."
    if max_len:
        return f"Длина не более {max_len} симв."
    return RULE_NAME

def validate(value, params=None):
    if pd.isna(value):
        value = ""
    s_value = str(value)
    length = len(s_value)
    if not params:
        return True
    min_len_str = params.get("min_length")
    max_len_str = params.get("max_length")
    if min_len_str:
        try:
            min_len = int(min_len_str)
            if length < min_len:
                return False
        except (ValueError, TypeError):
            pass
    if max_len_str:
        try:
            max_len = int(max_len_str)
            if length > max_len:
                return False
        except (ValueError, TypeError):
            pass
    return True