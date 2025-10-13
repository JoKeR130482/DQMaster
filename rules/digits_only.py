import pandas as pd

RULE_NAME = "Только цифры"
RULE_DESC = "Проверяет, что значение состоит только из цифр."

def validate(value):
    if pd.isna(value):
        return True
    s_value = str(value)
    if not s_value:
        return True
    return s_value.isdigit()