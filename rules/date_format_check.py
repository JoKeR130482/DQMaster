import pandas as pd
from datetime import datetime

RULE_NAME = "Проверка формата даты"
RULE_DESC = "Проверяет, соответствует ли значение заданному формату даты."
IS_CONFIGURABLE = True

PARAMS_SCHEMA = [
    {
        "name": "date_format",
        "type": "text",
        "label": "Формат даты (например, %d.%m.%Y)",
        "default": "%d.%m.%Y"
    }
]

def format_name(params):
    if not params or not params.get("date_format"):
        return RULE_NAME
    date_format = params.get("date_format")
    return f"Формат даты: {date_format}"

def validate(value, params=None):
    if pd.isna(value) or value == '':
        return True
    if not params or not params.get("date_format"):
        return True
    date_format = params.get("date_format")
    try:
        datetime.strptime(str(value), date_format)
        return True
    except (ValueError, TypeError):
        return False