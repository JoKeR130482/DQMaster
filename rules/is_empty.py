import pandas as pd

RULE_NAME = "Пустое"
RULE_DESC = "Проверяет, что значение в ячейке является пустым (null или пустая строка)."

def validate(value):
    """
    Checks if a value is null or an empty/whitespace-only string.
    """
    # Check for pandas/numpy null values (None, NaN, etc.)
    if pd.isna(value):
        return True

    # Check for empty or whitespace-only strings
    if isinstance(value, str) and not value.strip():
        return True

    return False