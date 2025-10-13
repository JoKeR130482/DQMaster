import pandas as pd

RULE_NAME = "Содержит хотя бы одну букву"
RULE_DESC = "Проверяет, что в значении есть хотя бы одна буква."

def validate(value):
    if pd.isna(value):
        return False
    s_value = str(value)
    return any(char.isalpha() for char in s_value)