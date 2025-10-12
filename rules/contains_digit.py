import pandas as pd

RULE_NAME = "Содержит хотя бы одну цифру"
RULE_DESC = "Проверяет, что в значении есть хотя бы одна цифра."

def validate(value):
    """
    Ошибка, если в строке нет ни одной цифры.
    """
    if pd.isna(value):
        return False # Пустое значение не содержит цифр

    s_value = str(value)

    # any() вернет True, если хотя бы один символ является цифрой
    return any(char.isdigit() for char in s_value)