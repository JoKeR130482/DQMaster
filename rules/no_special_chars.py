import re
import pandas as pd

RULE_NAME = "Без специальных символов"
RULE_DESC = "Проверяет, что значение не содержит специальных символов, кроме разрешенных."
IS_CONFIGURABLE = True

PARAMS_SCHEMA = [
    {
        "name": "allowed_chars",
        "type": "text",
        "label": "Дополнительные разрешенные символы",
        "default": "-_."
    }
]

def format_name(params):
    if not params or not params.get("allowed_chars"):
        return "Без спец. символов"
    allowed = params.get("allowed_chars")
    return f"Без спец. символов (кроме \\\"{allowed}\\\")"

def validate(value, params=None):
    if pd.isna(value):
        return True
    s_value = str(value)
    allowed_chars = params.get("allowed_chars", "-_.") if params else "-_."
    pattern = r'[^a-zA-Zа-яА-ЯёЁ0-9' + re.escape(allowed_chars) + r']'
    if re.search(pattern, s_value):
        return False
    return True