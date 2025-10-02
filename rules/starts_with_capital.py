import re

RULE_NAME = "Начинается с заглавной"
RULE_DESC = "Проверяет, что значение является строкой и начинается с заглавной буквы (кириллица или латиница)."

def validate(value):
    """
    Checks if a value is a string and starts with a capital letter.
    Non-string values are ignored (not considered invalid).
    """
    # This rule only applies to strings.
    if not isinstance(value, str):
        return True # Not an error for this rule if the cell is empty, a number, etc.

    # If it's an empty string, it doesn't start with a capital.
    if not value:
        return False

    # Regex for Cyrillic or Latin capital letter at the beginning of the string
    pattern = r'^[A-ZА-Я]'
    return re.match(pattern, value) is not None