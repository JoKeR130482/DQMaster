import pandas as pd

RULE_NAME = "Содержит хотя бы одну букву"
RULE_DESC = "Проверяет, что в значении есть хотя бы одна буква."

def validate(value):
    """
    Ошибка, если в строке нет ни одной буквы.
    """
    if pd.isna(value):
        return False # Пустое значение не содержит букв

    s_value = str(value)

    # any() вернет True, если хотя бы один символ является буквой
    return any(char.isalpha() for char in s_value)