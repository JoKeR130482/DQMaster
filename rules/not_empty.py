import pandas as pd

RULE_NAME = "Не пустое"
RULE_DESC = "Проверяет, что значение в ячейке не является пустым (не null и не пустая строка)."

def validate(value):
    """
    Checks if a value is not null and not an empty or whitespace-only string.
    """
    # Check for pandas/numpy null values (None, NaN, etc.)
    if pd.isna(value):
        return False

    # Check for empty or whitespace-only strings
    if isinstance(value, str) and not value.strip():
        return False

    return True