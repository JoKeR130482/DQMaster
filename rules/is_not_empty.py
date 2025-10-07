import pandas as pd

RULE_NAME = "Не пустое"
RULE_DESC = "Проверяет, что значение в ячейке не является пустым (null или пустая строка)."

def validate(value):
    """
    Checks that a value is NOT null or an empty/whitespace-only string.
    Returns False if the value is empty, triggering a validation error.
    """
    # Check for pandas/numpy null values (None, NaN, etc.)
    if pd.isna(value):
        return False

    # Check for empty or whitespace-only strings
    if isinstance(value, str) and not value.strip():
        return False

    return True