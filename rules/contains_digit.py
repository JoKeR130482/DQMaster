import pandas as pd

RULE_NAME = "Содержит хотя бы одну цифру"
RULE_DESC = "Проверяет, что в значении есть хотя бы одна цифра."

def validate(value):
    if pd.isna(value):
        return False
    s_value = str(value)
    return any(char.isdigit() for char in s_value)