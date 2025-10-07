import pandas as pd

RULE_NAME = "Не должно быть пустым"
RULE_DESC = "Проверяет, что значение в ячейке не является пустым. Пустые значения будут показаны как ошибки."

def validate(value):
    """
    Checks that a value is NOT null or an empty/whitespace-only string.
    This logic is inverted for the validation system:
    - It returns False for empty values, which triggers a validation error.
    - It returns True for non-empty values, which means they are valid.
    """
    # Check for pandas/numpy null values (None, NaN, etc.)
    if pd.isna(value):
        return False

    # Check for empty or whitespace-only strings
    if isinstance(value, str) and not value.strip():
        return False

    return True