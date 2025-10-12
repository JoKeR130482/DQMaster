import pandas as pd

RULE_NAME = "Только цифры"
RULE_DESC = "Проверяет, что значение состоит только из цифр."

def validate(value):
    """
    Ошибка, если строка содержит что-либо, кроме цифр.
    """
    if pd.isna(value):
        return True # Пустые значения пропускаем

    s_value = str(value)

    if not s_value:
        return True # Пустые строки пропускаем

    return s_value.isdigit()